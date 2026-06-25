import type { FeatureCollection, Point } from "geojson";
import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

import { FALLBACK_MAP_VIEW, getInitialMapView } from "../lib/mapGeolocation";
import { ensureMapLibreWorker } from "../lib/maplibreSetup";
import { applyGreyMapStyle } from "../lib/mapGreyStyle";
import { pinsBounds } from "../lib/mapState";
import type { LocationPinResponse, MapStateResponse } from "../lib/types";

const MAP_STYLE = "https://tiles.openfreemap.org/styles/liberty";
const GROUP_PINS_SOURCE_ID = "group-pins";
const GROUP_PINS_LAYER_ID = "group-pins-layer";

type WorldMapVariant = "landing" | "workspace";

type WorldMapProps = {
  variant?: WorldMapVariant;
  mapState?: MapStateResponse | null;
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

/**
 * Minimal grey geographic base map with streets and generic 3D building
 * footprints. User-generated models are layered on top in later roadmap
 * sections.
 */
export function WorldMap({ variant = "landing", mapState = null }: WorldMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const mapReadyRef = useRef(false);
  const mapStateRef = useRef(mapState);

  useEffect(() => {
    mapStateRef.current = mapState;
  }, [mapState]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) {
      return;
    }

    ensureMapLibreWorker();

    let disposed = false;
    mapReadyRef.current = false;

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
      mapReadyRef.current = true;
      map.resize();
    });

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
      mapReadyRef.current = false;
      mapRef.current = null;
      resizeObserver.disconnect();
      map.remove();
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !mapReadyRef.current) {
      return;
    }

    updateGroupPinLayer(map, mapState);

    if (variant === "workspace" && mapState?.pins?.length) {
      fitMapToPins(map, mapState.pins);
    }
  }, [mapState, variant]);

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
