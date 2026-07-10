import type {
  FeatureCollection,
  MultiPolygon,
  Polygon,
  Position,
} from "geojson";
import type { MapGeoJSONFeature, Map as MaplibreMap, PointLike } from "maplibre-gl";
import maplibregl from "maplibre-gl";
import booleanPointInPolygon from "@turf/boolean-point-in-polygon";
import flatten from "@turf/flatten";
import { point as turfPoint } from "@turf/helpers";

import type { BuildingIdentityStrategy, SelectedBuilding } from "./types";

/** Dev-only diagnostics for verifying tile identifiers are actually unique. */
const DEBUG_BUILDING_IDENTITY: boolean =
  typeof import.meta !== "undefined" && Boolean(import.meta.env?.DEV);

export const BUILDING_PICKER_LAYER_ID = "building-picker";
export const OPENMAPTILES_SOURCE_ID = "openmaptiles";
export const BUILDING_SOURCE_LAYER = "building";

export const SELECTABLE_BUILDINGS_SOURCE_ID = "selectable-buildings";
export const SELECTABLE_BUILDINGS_LAYER_ID = "selectable-buildings-outline";
export const HOVER_BUILDING_SOURCE_ID = "hover-building";
export const HOVER_BUILDING_LAYER_ID = "hover-building-outline";
export const SELECTED_BUILDING_SOURCE_ID = "selected-building";
export const SELECTED_BUILDING_LAYER_ID = "selected-building-outline";
export const BUILDING_HIGHLIGHT_ANCHOR_LAYER_ID = "building-highlight-anchor";

/** 2D layers used for hit-testing. Do not query fill-extrusion layers at pitch. */
export const BUILDING_QUERY_LAYER_IDS = [
  BUILDING_PICKER_LAYER_ID,
  "building",
] as const;

export const BUILDING_HIGHLIGHT_COLORS = {
  selectable: "#94a3b8",
  hover: "#2563eb",
  selected: "#059669",
} as const;

const QUERY_BBOX_PADDING_PX = 4;
const MAX_NEAREST_BUILDING_METERS = 35;

function extrusionLayerId(map: MaplibreMap): string | null {
  if (map.getLayer("building-3d")) {
    return "building-3d";
  }
  if (map.getLayer("grey-3d-buildings")) {
    return "grey-3d-buildings";
  }
  return null;
}

function layerIdAboveExtrusion(map: MaplibreMap): string | undefined {
  const extrusionId = extrusionLayerId(map);
  if (!extrusionId) {
    return undefined;
  }

  const layers = map.getStyle().layers ?? [];
  const extrusionIndex = layers.findIndex((layer) => layer.id === extrusionId);
  if (extrusionIndex === -1) {
    return undefined;
  }

  return layers[extrusionIndex + 1]?.id;
}

export function ensureBuildingHighlightAnchorLayer(map: MaplibreMap): void {
  if (map.getLayer(BUILDING_HIGHLIGHT_ANCHOR_LAYER_ID)) {
    return;
  }

  if (!map.getSource(OPENMAPTILES_SOURCE_ID)) {
    return;
  }

  map.addLayer(
    {
      id: BUILDING_HIGHLIGHT_ANCHOR_LAYER_ID,
      type: "fill",
      source: OPENMAPTILES_SOURCE_ID,
      "source-layer": BUILDING_SOURCE_LAYER,
      minzoom: 14,
      paint: {
        "fill-color": "#000000",
        "fill-opacity": 0,
      },
    },
    layerIdAboveExtrusion(map),
  );
}

export function ensureBuildingPickerLayer(map: MaplibreMap): void {
  if (map.getLayer(BUILDING_PICKER_LAYER_ID)) {
    return;
  }

  if (!map.getSource(OPENMAPTILES_SOURCE_ID)) {
    return;
  }

  const beforeLayerId = extrusionLayerId(map) ?? undefined;

  map.addLayer(
    {
      id: BUILDING_PICKER_LAYER_ID,
      source: OPENMAPTILES_SOURCE_ID,
      "source-layer": BUILDING_SOURCE_LAYER,
      type: "fill",
      minzoom: 14,
      paint: {
        "fill-color": "#000000",
        "fill-opacity": 0,
      },
    },
    beforeLayerId,
  );
}

export function getQueryableBuildingLayers(map: MaplibreMap): string[] {
  return BUILDING_QUERY_LAYER_IDS.filter((layerId) => map.getLayer(layerId) != null);
}

function ringCentroid(coords: Position[]): { lng: number; lat: number } {
  if (coords.length === 0) {
    return { lng: 0, lat: 0 };
  }

  const limit = coords.length > 1 ? coords.length - 1 : coords.length;
  let sumLng = 0;
  let sumLat = 0;

  for (let index = 0; index < limit; index += 1) {
    sumLng += coords[index][0];
    sumLat += coords[index][1];
  }

  return {
    lng: sumLng / limit,
    lat: sumLat / limit,
  };
}

export function centroidFromGeometry(
  geometry: Polygon | MultiPolygon,
): { lat: number; lng: number } {
  if (geometry.type === "Polygon") {
    const centroid = ringCentroid(geometry.coordinates[0] ?? []);
    return { lat: centroid.lat, lng: centroid.lng };
  }

  const centroid = ringCentroid(geometry.coordinates[0]?.[0] ?? []);
  return { lat: centroid.lat, lng: centroid.lng };
}

function parseNumericId(value: unknown): number | null {
  if (value == null || value === "") {
    return null;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

/** Round a coordinate to ~0.1m precision so tiny float noise is stable. */
function normalizeCoordinate(value: number): number {
  return Math.round(value * 1e6) / 1e6;
}

/** Deterministic 32-bit FNV-1a hash, rendered in base36. */
function hashString(input: string): string {
  let hash = 0x811c9dc5;
  for (let index = 0; index < input.length; index += 1) {
    hash ^= input.charCodeAt(index);
    hash = Math.imul(hash, 0x01000193);
  }
  return (hash >>> 0).toString(36);
}

/**
 * Build a deterministic hash of a footprint's coordinates. Two distinct
 * buildings produce different hashes even if they share (or lack) an osm_id,
 * which is what guarantees per-footprint uniqueness in the highlight layers.
 */
export function geometryHash(geometry: Polygon | MultiPolygon): string {
  const rings: Position[][] =
    geometry.type === "Polygon"
      ? geometry.coordinates
      : geometry.coordinates.flat();

  const parts: string[] = [geometry.type];
  for (const ring of rings) {
    for (const position of ring) {
      parts.push(
        `${normalizeCoordinate(position[0])},${normalizeCoordinate(position[1])}`,
      );
    }
    parts.push("|");
  }

  return hashString(parts.join(";"));
}

type FeatureLike = MapGeoJSONFeature | FeatureCollection["features"][number];

/**
 * Build a {@link SelectedBuilding} from a single footprint geometry, deriving
 * its identity from the owning feature. Because the geometry hash, centroid,
 * and selection key are all computed from `geometry`, callers must pass an
 * already-isolated polygon (not a tile-aggregated MultiPolygon) to get a
 * per-footprint result.
 */
function buildingFromGeometry(
  geometry: Polygon | MultiPolygon,
  feature: FeatureLike,
): SelectedBuilding {
  const centroid = centroidFromGeometry(geometry);
  const hash = geometryHash(geometry);

  const propertyOsmId = parseNumericId(feature.properties?.osm_id);
  const featureNumericId = parseNumericId(feature.id);

  let osmBuildingId: number | null;
  let identityStrategy: BuildingIdentityStrategy;
  let keyBody: string;

  if (propertyOsmId != null) {
    osmBuildingId = propertyOsmId;
    identityStrategy = "osm";
    keyBody = `${propertyOsmId}:${hash}`;
  } else if (featureNumericId != null) {
    osmBuildingId = featureNumericId;
    identityStrategy = "feature";
    keyBody = `${featureNumericId}:${hash}`;
  } else {
    osmBuildingId = null;
    identityStrategy = "geometry";
    keyBody = hash;
  }

  return {
    osmBuildingId,
    geometry,
    centroid,
    selectionKey: `${identityStrategy}:${keyBody}`,
    identityStrategy,
  };
}

export function buildingFromFeature(
  feature: FeatureLike,
): SelectedBuilding | null {
  const geometry = feature.geometry;
  if (geometry.type !== "Polygon" && geometry.type !== "MultiPolygon") {
    return null;
  }

  return buildingFromGeometry(geometry, feature);
}

/**
 * Explode an aggregated geometry into the individual footprints it contains.
 * OpenFreeMap frequently merges many disconnected buildings inside a tile into
 * one MultiPolygon; flattening restores one {@link Polygon} per footprint so we
 * can hit-test and highlight a single house instead of the whole cluster.
 */
export function explodeToPolygons(
  geometry: Polygon | MultiPolygon,
): Polygon[] {
  if (geometry.type === "Polygon") {
    return [geometry];
  }

  return flatten(geometry).features.map((feature) => feature.geometry);
}

/**
 * Isolate the single footprint under a lng/lat cursor position. For a
 * MultiPolygon we shatter it and keep only the sub-polygon containing the
 * cursor (smallest by area when several overlap). A plain Polygon is returned
 * as-is so existing single-footprint behavior is unchanged.
 */
export function isolatePolygonAtLngLat(
  geometry: Polygon | MultiPolygon,
  lng: number,
  lat: number,
): Polygon | null {
  const polygons = explodeToPolygons(geometry);
  if (polygons.length <= 1) {
    return polygons[0] ?? null;
  }

  const probe = turfPoint([lng, lat]);
  const containing = polygons.filter((polygon) =>
    booleanPointInPolygon(probe, polygon),
  );

  if (containing.length === 0) {
    return null;
  }

  return containing.reduce((best, candidate) =>
    polygonArea(candidate) < polygonArea(best) ? candidate : best,
  );
}

/**
 * Build a per-footprint {@link SelectedBuilding} for the geometry directly under
 * the cursor, discarding any tile-aggregated siblings. Returns null when the
 * cursor is not inside any isolated sub-polygon of a MultiPolygon.
 */
export function buildingFromFeatureAtLngLat(
  feature: FeatureLike,
  lng: number,
  lat: number,
): SelectedBuilding | null {
  const geometry = feature.geometry;
  if (geometry.type !== "Polygon" && geometry.type !== "MultiPolygon") {
    return null;
  }

  const isolated = isolatePolygonAtLngLat(geometry, lng, lat);
  if (!isolated) {
    return null;
  }

  return buildingFromGeometry(isolated, feature);
}

/** Explode a feature into one {@link SelectedBuilding} per individual footprint. */
function explodeFeatureToBuildings(feature: FeatureLike): SelectedBuilding[] {
  const geometry = feature.geometry;
  if (geometry.type !== "Polygon" && geometry.type !== "MultiPolygon") {
    return [];
  }

  return explodeToPolygons(geometry).map((polygon) =>
    buildingFromGeometry(polygon, feature),
  );
}

function ringArea(coords: Position[]): number {
  if (coords.length < 3) {
    return Number.POSITIVE_INFINITY;
  }

  let area = 0;
  for (let index = 0; index < coords.length - 1; index += 1) {
    const [x1, y1] = coords[index];
    const [x2, y2] = coords[index + 1];
    area += x1 * y2 - x2 * y1;
  }

  return Math.abs(area / 2);
}

function polygonArea(geometry: Polygon | MultiPolygon): number {
  if (geometry.type === "Polygon") {
    const [outer, ...holes] = geometry.coordinates;
    const outerArea = ringArea(outer ?? []);
    const holeArea = holes.reduce((sum, hole) => sum + ringArea(hole), 0);
    return Math.max(outerArea - holeArea, 0);
  }

  return geometry.coordinates.reduce(
    (sum, polygon) =>
      sum +
      polygonArea({
        type: "Polygon",
        coordinates: polygon,
      }),
    0,
  );
}

function pointInRing(point: Position, ring: Position[]): boolean {
  const [x, y] = point;
  let inside = false;

  for (let i = 0, j = ring.length - 1; i < ring.length; j = i, i += 1) {
    const [xi, yi] = ring[i];
    const [xj, yj] = ring[j];
    const intersects =
      yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi;
    if (intersects) {
      inside = !inside;
    }
  }

  return inside;
}

function pointInPolygonGeometry(
  point: Position,
  geometry: Polygon | MultiPolygon,
): boolean {
  if (geometry.type === "Polygon") {
    const [outer, ...holes] = geometry.coordinates;
    if (!outer || !pointInRing(point, outer)) {
      return false;
    }
    return holes.every((hole) => !pointInRing(point, hole));
  }

  return geometry.coordinates.some((polygon) =>
    pointInPolygonGeometry(point, {
      type: "Polygon",
      coordinates: polygon,
    }),
  );
}

function pickBestBuilding(
  map: MaplibreMap,
  point: PointLike,
  features: MapGeoJSONFeature[],
): SelectedBuilding | null {
  const lngLat = map.unproject(point);
  const probe: Position = [lngLat.lng, lngLat.lat];

  const candidates = features
    .map((feature) =>
      buildingFromFeatureAtLngLat(feature, lngLat.lng, lngLat.lat),
    )
    .filter((building): building is SelectedBuilding => building !== null);

  if (candidates.length === 0) {
    return null;
  }

  const containing = candidates.filter((building) =>
    pointInPolygonGeometry(probe, building.geometry),
  );
  const pool = containing.length > 0 ? containing : candidates;

  return pool.reduce((best, candidate) =>
    polygonArea(candidate.geometry) < polygonArea(best.geometry)
      ? candidate
      : best,
  );
}

/**
 * Dev-only: dump the identifiers of the features under the cursor so we can
 * confirm whether OpenFreeMap tiles expose a truly unique per-building id.
 */
function logBuildingIdentityDiagnostics(
  features: MapGeoJSONFeature[],
  picked: SelectedBuilding | null,
): void {
  if (!DEBUG_BUILDING_IDENTITY) {
    return;
  }

  const osmIds = features.map((feature) => feature.properties?.osm_id ?? null);
  const uniqueOsmIds = new Set(osmIds.filter((id) => id != null));

  console.debug("[building-identity]", {
    candidateCount: features.length,
    distinctOsmIds: uniqueOsmIds.size,
    sample: features.slice(0, 6).map((feature) => ({
      featureId: feature.id ?? null,
      osm_id: feature.properties?.osm_id ?? null,
      class: feature.properties?.class ?? null,
      geometryType: feature.geometry.type,
      propertyKeys: Object.keys(feature.properties ?? {}),
    })),
    picked: picked
      ? {
          selectionKey: picked.selectionKey,
          identityStrategy: picked.identityStrategy,
          osmBuildingId: picked.osmBuildingId,
        }
      : null,
  });
}

function queryRenderedBuildings(
  map: MaplibreMap,
  point: PointLike,
  debug = false,
): SelectedBuilding | null {
  const layers = getQueryableBuildingLayers(map);
  if (layers.length === 0) {
    return null;
  }

  const px = maplibregl.Point.convert(point);
  const bbox: [[number, number], [number, number]] = [
    [px.x - QUERY_BBOX_PADDING_PX, px.y - QUERY_BBOX_PADDING_PX],
    [px.x + QUERY_BBOX_PADDING_PX, px.y + QUERY_BBOX_PADDING_PX],
  ];

  const seen = new Set<string>();
  const features: MapGeoJSONFeature[] = [];

  for (const batch of [
    map.queryRenderedFeatures(point, { layers }),
    map.queryRenderedFeatures(bbox, { layers }),
  ]) {
    for (const feature of batch) {
      const building = buildingFromFeature(feature);
      if (!building || seen.has(building.selectionKey)) {
        continue;
      }
      seen.add(building.selectionKey);
      features.push(feature);
    }
  }

  const picked = pickBestBuilding(map, point, features);
  if (debug) {
    logBuildingIdentityDiagnostics(features, picked);
  }
  return picked;
}

function haversineMeters(
  lat1: number,
  lng1: number,
  lat2: number,
  lng2: number,
): number {
  const toRadians = (value: number) => (value * Math.PI) / 180;
  const earthRadius = 6_371_000;
  const dLat = toRadians(lat2 - lat1);
  const dLng = toRadians(lng2 - lng1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRadians(lat1)) *
      Math.cos(toRadians(lat2)) *
      Math.sin(dLng / 2) ** 2;

  return 2 * earthRadius * Math.asin(Math.sqrt(a));
}

function querySourceBuildingsAtLngLat(
  map: MaplibreMap,
  lng: number,
  lat: number,
): SelectedBuilding | null {
  if (!map.getSource(OPENMAPTILES_SOURCE_ID)) {
    return null;
  }

  const point: Position = [lng, lat];
  const features = map.querySourceFeatures(OPENMAPTILES_SOURCE_ID, {
    sourceLayer: BUILDING_SOURCE_LAYER,
  });

  let nearestMatch: SelectedBuilding | null = null;
  let nearestDistance = Number.POSITIVE_INFINITY;

  for (const feature of features) {
    const building = buildingFromFeature(feature);
    if (!building) {
      continue;
    }

    if (pointInPolygonGeometry(point, building.geometry)) {
      const isolated = buildingFromFeatureAtLngLat(feature, lng, lat);
      return isolated ?? building;
    }

    const distance = haversineMeters(
      lat,
      lng,
      building.centroid.lat,
      building.centroid.lng,
    );
    if (distance < nearestDistance) {
      nearestDistance = distance;
      nearestMatch = building;
    }
  }

  if (nearestMatch && nearestDistance <= MAX_NEAREST_BUILDING_METERS) {
    return nearestMatch;
  }

  return null;
}

function dedupeBuildingsFromFeatures(
  features: MapGeoJSONFeature[],
): SelectedBuilding[] {
  const seen = new Set<string>();
  const buildings: SelectedBuilding[] = [];

  for (const feature of features) {
    for (const building of explodeFeatureToBuildings(feature)) {
      if (seen.has(building.selectionKey)) {
        continue;
      }

      seen.add(building.selectionKey);
      buildings.push(building);
    }
  }

  return buildings;
}

function querySelectableBuildingsFromSource(
  map: MaplibreMap,
): SelectedBuilding[] {
  if (!map.getSource(OPENMAPTILES_SOURCE_ID)) {
    return [];
  }

  const bounds = map.getBounds();
  const features = map.querySourceFeatures(OPENMAPTILES_SOURCE_ID, {
    sourceLayer: BUILDING_SOURCE_LAYER,
  });

  const seen = new Set<string>();
  const buildings: SelectedBuilding[] = [];

  for (const feature of features) {
    for (const building of explodeFeatureToBuildings(feature)) {
      if (seen.has(building.selectionKey)) {
        continue;
      }

      const { lat, lng } = building.centroid;
      if (
        lng < bounds.getWest() ||
        lng > bounds.getEast() ||
        lat < bounds.getSouth() ||
        lat > bounds.getNorth()
      ) {
        continue;
      }

      seen.add(building.selectionKey);
      buildings.push(building);
    }
  }

  return buildings;
}

export function querySelectableBuildingsInView(
  map: MaplibreMap,
): SelectedBuilding[] {
  const layers = getQueryableBuildingLayers(map);
  if (layers.length > 0) {
    const canvas = map.getCanvas();
    const viewport: [[number, number], [number, number]] = [
      [0, 0],
      [canvas.width, canvas.height],
    ];
    const rendered = dedupeBuildingsFromFeatures(
      map.queryRenderedFeatures(viewport, { layers }),
    );

    if (rendered.length > 0) {
      return rendered;
    }
  }

  return querySelectableBuildingsFromSource(map);
}

export function queryBuildingHoverAtPoint(
  map: MaplibreMap,
  point: PointLike,
): SelectedBuilding | null {
  return queryRenderedBuildings(map, point);
}

export function queryBuildingAtPoint(
  map: MaplibreMap,
  point: PointLike,
): SelectedBuilding | null {
  const renderedMatch = queryRenderedBuildings(map, point, true);
  if (renderedMatch) {
    return renderedMatch;
  }

  const lngLat = map.unproject(point);
  return querySourceBuildingsAtLngLat(map, lngLat.lng, lngLat.lat);
}

function buildingsToFeatureCollection(
  buildings: SelectedBuilding[],
): FeatureCollection {
  return {
    type: "FeatureCollection",
    features: buildings.map((building) => ({
      type: "Feature",
      geometry: building.geometry,
      properties: {
        osm_building_id: building.osmBuildingId,
        selection_key: building.selectionKey,
      },
    })),
  };
}

function buildingToFeatureCollection(
  building: SelectedBuilding | null,
): FeatureCollection {
  if (!building) {
    return { type: "FeatureCollection", features: [] };
  }

  return buildingsToFeatureCollection([building]);
}

function upsertLineLayer(
  map: MaplibreMap,
  sourceId: string,
  layerId: string,
  data: FeatureCollection,
  paint: maplibregl.LineLayerSpecification["paint"],
  beforeLayerId?: string,
): void {
  const existingSource = map.getSource(sourceId);

  if (existingSource instanceof maplibregl.GeoJSONSource) {
    if (data.features.length === 0) {
      clearLineLayer(map, sourceId, layerId);
      return;
    }

    existingSource.setData(data);
    if (!map.getLayer(layerId) && data.features.length > 0) {
      map.addLayer(
        {
          id: layerId,
          type: "line",
          source: sourceId,
          paint,
        },
        beforeLayerId,
      );
    }
    return;
  }

  if (data.features.length === 0) {
    return;
  }

  map.addSource(sourceId, {
    type: "geojson",
    data,
  });

  map.addLayer(
    {
      id: layerId,
      type: "line",
      source: sourceId,
      paint,
    },
    beforeLayerId,
  );
}

function clearLineLayer(
  map: MaplibreMap,
  sourceId: string,
  layerId: string,
): void {
  if (map.getLayer(layerId)) {
    map.removeLayer(layerId);
  }
  if (map.getSource(sourceId)) {
    map.removeSource(sourceId);
  }
}

function findTopHighlightBeforeId(map: MaplibreMap): string | undefined {
  ensureBuildingHighlightAnchorLayer(map);
  if (map.getLayer(BUILDING_HIGHLIGHT_ANCHOR_LAYER_ID)) {
    return BUILDING_HIGHLIGHT_ANCHOR_LAYER_ID;
  }
  if (map.getLayer("group-pins-layer")) {
    return "group-pins-layer";
  }
  return undefined;
}

export function updateSelectableBuildingsLayer(
  map: MaplibreMap,
  buildings: SelectedBuilding[],
  excludeSelectionKey?: string | null,
): void {
  const filtered = excludeSelectionKey
    ? buildings.filter(
        (building) => building.selectionKey !== excludeSelectionKey,
      )
    : buildings;

  if (filtered.length === 0) {
    clearLineLayer(map, SELECTABLE_BUILDINGS_SOURCE_ID, SELECTABLE_BUILDINGS_LAYER_ID);
    return;
  }

  upsertLineLayer(
    map,
    SELECTABLE_BUILDINGS_SOURCE_ID,
    SELECTABLE_BUILDINGS_LAYER_ID,
    buildingsToFeatureCollection(filtered),
    {
      "line-color": BUILDING_HIGHLIGHT_COLORS.selectable,
      "line-width": 2,
      "line-opacity": 0.95,
    },
    findTopHighlightBeforeId(map),
  );
}

export function updateHoverBuildingLayer(
  map: MaplibreMap,
  building: SelectedBuilding | null,
): void {
  if (!building) {
    clearLineLayer(map, HOVER_BUILDING_SOURCE_ID, HOVER_BUILDING_LAYER_ID);
    return;
  }

  upsertLineLayer(
    map,
    HOVER_BUILDING_SOURCE_ID,
    HOVER_BUILDING_LAYER_ID,
    buildingToFeatureCollection(building),
    {
      "line-color": BUILDING_HIGHLIGHT_COLORS.hover,
      "line-width": 3,
      "line-opacity": 1,
    },
    findTopHighlightBeforeId(map),
  );
}

export function updateSelectedBuildingLayer(
  map: MaplibreMap,
  building: SelectedBuilding | null,
): void {
  if (!building) {
    clearLineLayer(map, SELECTED_BUILDING_SOURCE_ID, SELECTED_BUILDING_LAYER_ID);
    return;
  }

  upsertLineLayer(
    map,
    SELECTED_BUILDING_SOURCE_ID,
    SELECTED_BUILDING_LAYER_ID,
    buildingToFeatureCollection(building),
    {
      "line-color": BUILDING_HIGHLIGHT_COLORS.selected,
      "line-width": 3.5,
      "line-opacity": 1,
    },
    findTopHighlightBeforeId(map),
  );
}

export function clearAllBuildingHighlightLayers(map: MaplibreMap): void {
  clearLineLayer(map, SELECTABLE_BUILDINGS_SOURCE_ID, SELECTABLE_BUILDINGS_LAYER_ID);
  clearLineLayer(map, HOVER_BUILDING_SOURCE_ID, HOVER_BUILDING_LAYER_ID);
  clearLineLayer(map, SELECTED_BUILDING_SOURCE_ID, SELECTED_BUILDING_LAYER_ID);
}
