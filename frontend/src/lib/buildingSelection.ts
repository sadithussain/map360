import type {
  FeatureCollection,
  MultiPolygon,
  Polygon,
  Position,
} from "geojson";
import type { MapGeoJSONFeature, Map as MaplibreMap, PointLike } from "maplibre-gl";
import maplibregl from "maplibre-gl";

import type { SelectedBuilding } from "./types";

export const BUILDING_PICKER_LAYER_ID = "building-picker";
export const OPENMAPTILES_SOURCE_ID = "openmaptiles";
export const BUILDING_SOURCE_LAYER = "building";

/** 2D layers used for hit-testing. Do not query fill-extrusion layers at pitch. */
export const BUILDING_QUERY_LAYER_IDS = [
  BUILDING_PICKER_LAYER_ID,
  "building",
] as const;

export const SELECTED_BUILDING_SOURCE_ID = "selected-building";
export const SELECTED_BUILDING_LAYER_ID = "selected-building-highlight";
export const HOVER_BUILDING_SOURCE_ID = "hover-building";
export const HOVER_BUILDING_LAYER_ID = "hover-building-highlight";

const QUERY_BBOX_PADDING_PX = 8;
const MAX_NEAREST_BUILDING_METERS = 35;

export function ensureBuildingPickerLayer(map: MaplibreMap): void {
  if (map.getLayer(BUILDING_PICKER_LAYER_ID)) {
    return;
  }

  if (!map.getSource(OPENMAPTILES_SOURCE_ID)) {
    return;
  }

  const beforeLayerId = map.getLayer("building-3d")
    ? "building-3d"
    : map.getLayer("grey-3d-buildings")
      ? "grey-3d-buildings"
      : undefined;

  map.addLayer(
    {
      id: BUILDING_PICKER_LAYER_ID,
      source: OPENMAPTILES_SOURCE_ID,
      "source-layer": BUILDING_SOURCE_LAYER,
      type: "fill",
      minzoom: 14,
      paint: {
        "fill-color": "#c4c4c4",
        "fill-opacity": 0.01,
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

function resolveOsmBuildingId(
  feature: MapGeoJSONFeature | FeatureCollection["features"][number],
): number | null {
  const propertyId = feature.properties?.osm_id;
  if (propertyId != null && propertyId !== "") {
    const parsed = Number(propertyId);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }

  if (feature.id != null && feature.id !== "") {
    const parsed = Number(feature.id);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }

  return null;
}

export function buildingFromFeature(
  feature: MapGeoJSONFeature | FeatureCollection["features"][number],
): SelectedBuilding | null {
  const osmBuildingId = resolveOsmBuildingId(feature);
  if (osmBuildingId == null) {
    return null;
  }

  const geometry = feature.geometry;
  if (geometry.type !== "Polygon" && geometry.type !== "MultiPolygon") {
    return null;
  }

  return {
    osmBuildingId,
    geometry,
    centroid: centroidFromGeometry(geometry),
  };
}

function queryRenderedBuildings(
  map: MaplibreMap,
  point: PointLike,
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

  const queries = [
    map.queryRenderedFeatures(point, { layers }),
    map.queryRenderedFeatures(bbox, { layers }),
  ];

  for (const features of queries) {
    for (const feature of features) {
      const building = buildingFromFeature(feature);
      if (building) {
        return building;
      }
    }
  }

  return null;
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
      return building;
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
  const renderedMatch = queryRenderedBuildings(map, point);
  if (renderedMatch) {
    return renderedMatch;
  }

  const lngLat = map.unproject(point);
  return querySourceBuildingsAtLngLat(map, lngLat.lng, lngLat.lat);
}

function buildingToFeatureCollection(
  building: SelectedBuilding | null,
): FeatureCollection {
  if (!building) {
    return { type: "FeatureCollection", features: [] };
  }

  return {
    type: "FeatureCollection",
    features: [
      {
        type: "Feature",
        geometry: building.geometry,
        properties: {
          osm_building_id: building.osmBuildingId,
        },
      },
    ],
  };
}

export function upsertBuildingHighlightLayer(
  map: MaplibreMap,
  sourceId: string,
  layerId: string,
  building: SelectedBuilding | null,
  paint: Record<string, unknown>,
): void {
  const data = buildingToFeatureCollection(building);
  const existingSource = map.getSource(sourceId);

  if (existingSource instanceof maplibregl.GeoJSONSource) {
    existingSource.setData(data);
    return;
  }

  if (!building) {
    return;
  }

  map.addSource(sourceId, {
    type: "geojson",
    data,
  });

  map.addLayer({
    id: layerId,
    type: "fill",
    source: sourceId,
    paint,
  });
}

export function clearBuildingHighlightLayer(
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
