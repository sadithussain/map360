import type { Map } from "maplibre-gl";

import { ensureBuildingPickerLayer } from "./buildingSelection";

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
        "fill-extrusion-height": ["get", "render_height"],
        "fill-extrusion-base": ["get", "render_min_height"],
        "fill-extrusion-opacity": 0.85,
      },
    });
  }

  ensureBuildingPickerLayer(map);

  for (const layerId of LABEL_LAYER_IDS) {
    setLayoutIfExists(map, layerId, "visibility", "none");
  }

  setLayoutIfExists(map, "road_one_way_arrow", "visibility", "none");
  setLayoutIfExists(map, "road_one_way_arrow_opposite", "visibility", "none");
}
