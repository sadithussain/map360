import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

import { FALLBACK_MAP_VIEW, getInitialMapView } from "../lib/mapGeolocation";
import { ensureMapLibreWorker } from "../lib/maplibreSetup";
import { applyGreyMapStyle } from "../lib/mapGreyStyle";

const MAP_STYLE = "https://tiles.openfreemap.org/styles/liberty";

type WorldMapVariant = "landing" | "workspace";

type WorldMapProps = {
  variant?: WorldMapVariant;
};

/**
 * Minimal grey geographic base map with streets and generic 3D building
 * footprints. User-generated models are layered on top in later roadmap
 * sections.
 */
export function WorldMap({ variant = "landing" }: WorldMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) {
      return;
    }

    ensureMapLibreWorker();

    let disposed = false;

    const map = new maplibregl.Map({
      container,
      style: MAP_STYLE,
      center: [FALLBACK_MAP_VIEW.lng, FALLBACK_MAP_VIEW.lat],
      zoom: FALLBACK_MAP_VIEW.zoom,
      pitch: 60,
      bearing: -20,
    });

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
      resizeObserver.disconnect();
      map.remove();
    };
  }, []);

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
