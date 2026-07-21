import type { FeatureCollection, Point } from "geojson";
import { useCallback, useEffect, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

import {
  clearAllBuildingHighlightLayers,
  OPENMAPTILES_SOURCE_ID,
  queryBuildingAtPoint,
  queryBuildingHoverAtPoint,
  querySelectableBuildingsInView,
  updateHoverBuildingLayer,
  updateSelectableBuildingsLayer,
  updateSelectedBuildingLayer,
} from "../lib/buildingSelection";
import { FALLBACK_MAP_VIEW, getInitialMapView } from "../lib/mapGeolocation";
import { ensureMapLibreWorker } from "../lib/maplibreSetup";
import { applyGreyMapStyle } from "../lib/mapGreyStyle";
import { pinsBounds } from "../lib/mapState";
import type { LocationPinResponse, MapStateResponse, SelectedBuilding } from "../lib/types";

const MAP_STYLE = "https://tiles.openfreemap.org/styles/liberty";
const GROUP_PINS_SOURCE_ID = "group-pins";
const GROUP_PINS_LAYER_ID = "group-pins-layer";
const SELECTION_PITCH = 0;
const CAMERA_ANIMATION_MS = 500;

type SavedCamera = {
  pitch: number;
  bearing: number;
};

type WorldMapVariant = "landing" | "workspace";

export type BuildingSelectionPhase = "off" | "choosing" | "chosen";

type WorldMapProps = {
  variant?: WorldMapVariant;
  mapState?: MapStateResponse | null;
  buildingSelectionPhase?: BuildingSelectionPhase;
  selectedBuilding?: SelectedBuilding | null;
  onBuildingSelect?: (building: SelectedBuilding) => void;
  onMissedBuildingClick?: () => void;
};

function pinsToGeoJSON(
  pins: LocationPinResponse[] | undefined,
): FeatureCollection<Point> {
  return {
    type: "FeatureCollection",
    features: (pins ?? []).map((pin) => ({
      type: "Feature",
      geometry: {
        type: "Point",
        coordinates: [pin.lng, pin.lat],
      },
      properties: {
        label: pin.label ?? "",
        osm_building_id: pin.osm_building_id,
      },
    })),
  };
}

function updateGroupPinLayer(
  map: maplibregl.Map,
  mapState: MapStateResponse | null | undefined,
): void {
  const data = pinsToGeoJSON(mapState?.pins);
  const existingSource = map.getSource(GROUP_PINS_SOURCE_ID);

  if (existingSource instanceof maplibregl.GeoJSONSource) {
    existingSource.setData(data);
    return;
  }

  map.addSource(GROUP_PINS_SOURCE_ID, {
    type: "geojson",
    data,
  });

  map.addLayer({
    id: GROUP_PINS_LAYER_ID,
    type: "circle",
    source: GROUP_PINS_SOURCE_ID,
    paint: {
      "circle-radius": 8,
      "circle-color": "#4f46e5",
      "circle-stroke-width": 2,
      "circle-stroke-color": "#ffffff",
    },
  });
}

function fitMapToPins(
  map: maplibregl.Map,
  pins: LocationPinResponse[] | undefined,
): void {
  const bounds = pinsBounds(pins ?? []);
  if (!bounds) {
    return;
  }

  map.fitBounds(bounds, {
    padding: 80,
    maxZoom: 16,
    duration: 800,
  });
}

export function WorldMap({
  variant = "landing",
  mapState = null,
  buildingSelectionPhase = "off",
  selectedBuilding = null,
  onBuildingSelect,
  onMissedBuildingClick,
}: WorldMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const [mapReady, setMapReady] = useState(false);
  const mapStateRef = useRef(mapState);
  const buildingSelectionPhaseRef = useRef(buildingSelectionPhase);
  const selectedBuildingRef = useRef(selectedBuilding);
  const onBuildingSelectRef = useRef(onBuildingSelect);
  const onMissedBuildingClickRef = useRef(onMissedBuildingClick);
  const hoveredBuildingRef = useRef<SelectedBuilding | null>(null);
  const selectableBuildingsRef = useRef<SelectedBuilding[]>([]);
  const savedCameraRef = useRef<SavedCamera | null>(null);
  const refreshSelectableBuildingsRef = useRef<(map: maplibregl.Map) => void>(
    () => undefined,
  );
  const syncBuildingSelectionVisualsRef = useRef<
    (map: maplibregl.Map, phase: BuildingSelectionPhase, building: SelectedBuilding | null) => void
  >(() => undefined);

  useEffect(() => {
    mapStateRef.current = mapState;
  }, [mapState]);

  useEffect(() => {
    buildingSelectionPhaseRef.current = buildingSelectionPhase;
  }, [buildingSelectionPhase]);

  useEffect(() => {
    selectedBuildingRef.current = selectedBuilding;
  }, [selectedBuilding]);

  useEffect(() => {
    onBuildingSelectRef.current = onBuildingSelect;
  }, [onBuildingSelect]);

  useEffect(() => {
    onMissedBuildingClickRef.current = onMissedBuildingClick;
  }, [onMissedBuildingClick]);

  const refreshSelectableBuildings = useCallback((map: maplibregl.Map) => {
    if (buildingSelectionPhaseRef.current !== "choosing") {
      return;
    }

    const buildings = querySelectableBuildingsInView(map);
    selectableBuildingsRef.current = buildings;
    updateSelectableBuildingsLayer(
      map,
      buildings,
      hoveredBuildingRef.current?.selectionKey ?? null,
    );
  }, []);

  refreshSelectableBuildingsRef.current = refreshSelectableBuildings;

  const applySelectionCamera = useCallback(
    (map: maplibregl.Map, phase: BuildingSelectionPhase) => {
      if (phase === "off") {
        const saved = savedCameraRef.current;
        if (!saved) {
          return;
        }

        map.easeTo({
          pitch: saved.pitch,
          bearing: saved.bearing,
          duration: CAMERA_ANIMATION_MS,
          essential: true,
        });
        savedCameraRef.current = null;
        return;
      }

      if (phase === "choosing" && savedCameraRef.current == null) {
        savedCameraRef.current = {
          pitch: map.getPitch(),
          bearing: map.getBearing(),
        };
      }

      if (map.getPitch() > 1) {
        map.easeTo({
          pitch: SELECTION_PITCH,
          duration: CAMERA_ANIMATION_MS,
          essential: true,
        });
      }
    },
    [],
  );

  const syncBuildingSelectionVisuals = useCallback(
    (
      map: maplibregl.Map,
      phase: BuildingSelectionPhase,
      building: SelectedBuilding | null,
    ) => {
      hoveredBuildingRef.current = null;
      map.getCanvas().style.cursor = "";

      if (phase === "off") {
        clearAllBuildingHighlightLayers(map);
        selectableBuildingsRef.current = [];
        return;
      }

      if (phase === "choosing") {
        updateHoverBuildingLayer(map, null);
        updateSelectedBuildingLayer(map, null);
        refreshSelectableBuildings(map);
        return;
      }

      if (phase === "chosen") {
        updateSelectableBuildingsLayer(map, [], null);
        updateHoverBuildingLayer(map, null);
        updateSelectedBuildingLayer(map, building);
        selectableBuildingsRef.current = [];
      }
    },
    [refreshSelectableBuildings],
  );

  syncBuildingSelectionVisualsRef.current = syncBuildingSelectionVisuals;

  useEffect(() => {
    const container = containerRef.current;
    if (!container) {
      return;
    }

    ensureMapLibreWorker();

    let disposed = false;
    setMapReady(false);

    const map = new maplibregl.Map({
      container,
      style: MAP_STYLE,
      center: [FALLBACK_MAP_VIEW.lng, FALLBACK_MAP_VIEW.lat],
      zoom: FALLBACK_MAP_VIEW.zoom,
      pitch: 60,
      bearing: -20,
    });

    mapRef.current = map;
    map.addControl(new maplibregl.NavigationControl(), "top-right");

    // The OpenFreeMap Liberty style references POI icons (e.g. "office",
    // "gate", "atm") that are absent from its sprite sheet. We hide those POI
    // layers in the grey style, but MapLibre still requests the icons on first
    // paint. Register a transparent 1x1 placeholder for any missing image to
    // avoid noisy "Image could not be loaded" console errors.
    const handleStyleImageMissing = (event: { id: string }) => {
      if (map.hasImage(event.id)) {
        return;
      }
      map.addImage(event.id, {
        width: 1,
        height: 1,
        data: new Uint8Array(4),
      });
    };
    map.on("styleimagemissing", handleStyleImageMissing);

    let refreshTimer: number | undefined;

    const scheduleSelectableRefresh = () => {
      if (buildingSelectionPhaseRef.current !== "choosing") {
        return;
      }

      window.clearTimeout(refreshTimer);
      refreshTimer = window.setTimeout(() => {
        refreshSelectableBuildingsRef.current(map);
      }, 150);
    };

    const handleSourceData = (event: maplibregl.MapSourceDataEvent) => {
      if (event.sourceId !== OPENMAPTILES_SOURCE_ID || !event.isSourceLoaded) {
        return;
      }

      scheduleSelectableRefresh();
    };

    const handleClick = (event: maplibregl.MapMouseEvent) => {
      if (buildingSelectionPhaseRef.current !== "choosing") {
        return;
      }

      const building = queryBuildingAtPoint(map, event.point);
      if (building) {
        onBuildingSelectRef.current?.(building);
        return;
      }

      onMissedBuildingClickRef.current?.();
    };

    const handleMouseMove = (event: maplibregl.MapMouseEvent) => {
      if (buildingSelectionPhaseRef.current !== "choosing") {
        map.getCanvas().style.cursor = "";
        return;
      }

      const building = queryBuildingHoverAtPoint(map, event.point);
      if (building) {
        map.getCanvas().style.cursor = "pointer";
        if (
          hoveredBuildingRef.current?.selectionKey !== building.selectionKey
        ) {
          hoveredBuildingRef.current = building;
          updateHoverBuildingLayer(map, building);
          updateSelectableBuildingsLayer(
            map,
            selectableBuildingsRef.current,
            building.selectionKey,
          );
        }
        return;
      }

      map.getCanvas().style.cursor = "";
      if (hoveredBuildingRef.current) {
        hoveredBuildingRef.current = null;
        updateHoverBuildingLayer(map, null);
        updateSelectableBuildingsLayer(
          map,
          selectableBuildingsRef.current,
          null,
        );
      }
    };

    map.on("load", () => {
      if (disposed) {
        return;
      }

      try {
        applyGreyMapStyle(map);
      } catch (error) {
        console.error("Failed to apply grey map style:", error);
      }

      updateGroupPinLayer(map, mapStateRef.current);
      setMapReady(true);
      map.resize();

      syncBuildingSelectionVisualsRef.current(
        map,
        buildingSelectionPhaseRef.current,
        selectedBuildingRef.current,
      );
    });

    map.on("click", handleClick);
    map.on("mousemove", handleMouseMove);
    map.on("moveend", scheduleSelectableRefresh);
    map.on("zoomend", scheduleSelectableRefresh);
    map.on("sourcedata", handleSourceData);

    map.on("error", (event) => {
      console.error("MapLibre error:", event.error);
    });

    const resizeObserver = new ResizeObserver(() => {
      map.resize();
    });
    resizeObserver.observe(container);

    void getInitialMapView().then((view) => {
      if (disposed) {
        return;
      }

      map.flyTo({
        center: [view.lng, view.lat],
        zoom: view.zoom,
        essential: true,
      });
    });

    return () => {
      disposed = true;
      setMapReady(false);
      mapRef.current = null;
      window.clearTimeout(refreshTimer);
      resizeObserver.disconnect();
      map.off("click", handleClick);
      map.off("mousemove", handleMouseMove);
      map.off("moveend", scheduleSelectableRefresh);
      map.off("zoomend", scheduleSelectableRefresh);
      map.off("sourcedata", handleSourceData);
      map.off("styleimagemissing", handleStyleImageMissing);
      map.remove();
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) {
      return;
    }

    updateGroupPinLayer(map, mapState);

    if (variant === "workspace" && mapState?.pins?.length) {
      fitMapToPins(map, mapState.pins);
    }
  }, [mapState, variant, mapReady]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReady) {
      return;
    }

    applySelectionCamera(map, buildingSelectionPhase);
    syncBuildingSelectionVisuals(map, buildingSelectionPhase, selectedBuilding);
  }, [
    buildingSelectionPhase,
    selectedBuilding,
    mapReady,
    applySelectionCamera,
    syncBuildingSelectionVisuals,
  ]);

  return (
    <div className="relative h-full w-full">
      <div ref={containerRef} className="h-full w-full" />

      {variant === "landing" && (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
          <h1 className="text-center text-5xl font-bold tracking-tight text-white drop-shadow-lg sm:text-6xl">
            Generate Your World
          </h1>
        </div>
      )}
    </div>
  );
}
