import type { ExpressionSpecification, FilterSpecification, Map } from "maplibre-gl";

import {
  ensureBuildingHighlightAnchorLayer,
  ensureBuildingPickerLayer,
} from "./buildingSelection";

// Some OpenMapTiles building features have null/missing render_height or
// render_min_height. Coalescing to 0 avoids MapLibre's worker throwing
// "Expected value to be of type number, but found null instead".
const EXTRUSION_HEIGHT: ExpressionSpecification = [
  "coalesce",
  ["to-number", ["get", "render_height"]],
  0,
];

const EXTRUSION_BASE: ExpressionSpecification = [
  "coalesce",
  ["to-number", ["get", "render_min_height"]],
  0,
];

function setPaintIfExists(
  map: Map,
  layerId: string,
  property: string,
  value: unknown,
): void {
  if (map.getLayer(layerId)) {
    map.setPaintProperty(layerId, property, value);
  }
}

function setLayoutIfExists(
  map: Map,
  layerId: string,
  property: string,
  value: unknown,
): void {
  if (map.getLayer(layerId)) {
    map.setLayoutProperty(layerId, property, value);
  }
}

const LABEL_LAYER_IDS = [
  "waterway_line_label",
  "water_name_point_label",
  "water_name_line_label",
  "poi_r20",
  "poi_r7",
  "poi_r1",
  "poi_transit",
  "highway-name-path",
  "highway-name-minor",
  "highway-name-major",
  "highway-shield-non-us",
  "highway-shield-us-interstate",
  "road_shield_us",
  "airport",
  "label_other",
  "label_village",
  "label_town",
  "label_state",
  "label_city",
  "label_city_capital",
  "label_country_3",
  "label_country_2",
  "label_country_1",
];

const LANDUSE_FILL_LAYER_IDS = [
  "park",
  "landuse_residential",
  "landcover_wood",
  "landcover_grass",
  "landcover_ice",
  "landcover_wetland",
  "landuse_pitch",
  "landuse_track",
  "landuse_cemetery",
  "landuse_hospital",
  "landuse_school",
  "landcover_sand",
  "aeroway_fill",
  "road_area_pattern",
];

const ROAD_LINE_LAYER_IDS = [
  "road_motorway_link_casing",
  "road_service_track_casing",
  "road_link_casing",
  "road_minor_casing",
  "road_secondary_tertiary_casing",
  "road_trunk_primary_casing",
  "road_motorway_casing",
  "road_path_pedestrian",
  "road_motorway_link",
  "road_service_track",
  "road_link",
  "road_minor",
  "road_secondary_tertiary",
  "road_trunk_primary",
  "road_motorway",
  "road_major_rail",
  "road_major_rail_hatching",
  "road_transit_rail",
  "road_transit_rail_hatching",
];

export function applyGreyMapStyle(map: Map): void {
  setPaintIfExists(map, "background", "background-color", "#e8e8e8");
  setLayoutIfExists(map, "natural_earth", "visibility", "none");

  setPaintIfExists(map, "water", "fill-color", "#d0d0d0");

  for (const layerId of LANDUSE_FILL_LAYER_IDS) {
    setPaintIfExists(map, layerId, "fill-color", "#e0e0e0");
    setPaintIfExists(map, layerId, "fill-opacity", 0.6);
  }

  setPaintIfExists(map, "park_outline", "line-color", "#d8d8d8");

  for (const layerId of ROAD_LINE_LAYER_IDS) {
    if (layerId.includes("casing")) {
      setPaintIfExists(map, layerId, "line-color", "#b0b0b0");
    } else if (layerId.includes("rail")) {
      setPaintIfExists(map, layerId, "line-color", "#aaaaaa");
    } else {
      setPaintIfExists(map, layerId, "line-color", "#f5f5f5");
    }
  }

  setPaintIfExists(map, "building", "fill-color", "#c4c4c4");
  setPaintIfExists(map, "building", "fill-outline-color", "#a8a8a8");

  if (map.getLayer("building-3d")) {
    setPaintIfExists(map, "building-3d", "fill-extrusion-color", "#b8b8b8");
    setPaintIfExists(map, "building-3d", "fill-extrusion-opacity", 0.85);
    setPaintIfExists(map, "building-3d", "fill-extrusion-height", EXTRUSION_HEIGHT);
    setPaintIfExists(map, "building-3d", "fill-extrusion-base", EXTRUSION_BASE);
  } else {
    map.addLayer({
      id: "grey-3d-buildings",
      source: "openmaptiles",
      "source-layer": "building",
      filter: ["==", "extrude", "true"],
      type: "fill-extrusion",
      minzoom: 14,
      paint: {
        "fill-extrusion-color": "#b8b8b8",
        "fill-extrusion-height": EXTRUSION_HEIGHT,
        "fill-extrusion-base": EXTRUSION_BASE,
        "fill-extrusion-opacity": 0.85,
      },
    });
  }

  ensureBuildingPickerLayer(map);
  ensureBuildingHighlightAnchorLayer(map);

  for (const layerId of LABEL_LAYER_IDS) {
    setLayoutIfExists(map, layerId, "visibility", "none");
  }

  setLayoutIfExists(map, "road_one_way_arrow", "visibility", "none");
  setLayoutIfExists(map, "road_one_way_arrow_opposite", "visibility", "none");
}

// Default gray building layers whose footprints must be hidden wherever a
// contributed mesh is placed, so the generated model does not intersect the
// stock extrusion or show a gray footprint underneath.
const HIDEABLE_BUILDING_LAYER_IDS = ["building", "building-3d", "grey-3d-buildings"];

// The base filter of each hideable layer, captured before we add any osm_id
// exclusion so re-applying never nests filters. Keyed per map instance since
// the app can mount more than one map (landing + workspace).
const baseBuildingFilters = new WeakMap<
  Map,
  globalThis.Map<string, FilterSpecification | null>
>();

function baseBuildingFilter(map: Map, layerId: string): FilterSpecification | null {
  let perMap = baseBuildingFilters.get(map);
  if (!perMap) {
    perMap = new globalThis.Map();
    baseBuildingFilters.set(map, perMap);
  }
  if (!perMap.has(layerId)) {
    const current = map.getFilter(layerId) as FilterSpecification | undefined;
    perMap.set(layerId, current ?? null);
  }
  return perMap.get(layerId) ?? null;
}

/**
 * Hide the default gray buildings that match the given OSM building ids, so
 * user-generated meshes replace (rather than intersect) the stock footprints.
 *
 * Pass an empty array to restore all default buildings. Compares as strings to
 * tolerate numeric-vs-string ``osm_id`` typing across tile sources.
 */
export function setHiddenBuildingIds(map: Map, osmIds: number[]): void {
  const stringIds = osmIds
    .filter((id) => Number.isFinite(id))
    .map((id) => String(id));

  // A building id may have been captured from the tile's ``osm_id`` property or
  // from its raw feature id (see buildingSelection). Exclude a footprint when
  // either identifier matches a contributed building, comparing as strings to
  // tolerate numeric-vs-string typing.
  const exclusion: ExpressionSpecification | null =
    stringIds.length === 0
      ? null
      : [
          "!",
          [
            "any",
            ["in", ["to-string", ["coalesce", ["get", "osm_id"], ""]], ["literal", stringIds]],
            ["in", ["to-string", ["id"]], ["literal", stringIds]],
          ],
        ];

  for (const layerId of HIDEABLE_BUILDING_LAYER_IDS) {
    if (!map.getLayer(layerId)) {
      continue;
    }

    const base = baseBuildingFilter(map, layerId);
    if (exclusion === null) {
      map.setFilter(layerId, base);
      continue;
    }

    // In the Liberty style these layers have no base filter; when one exists we
    // combine so the original visibility rule is preserved alongside the hide.
    const combined = (base ? ["all", base, exclusion] : exclusion) as FilterSpecification;
    map.setFilter(layerId, combined);
  }
}
