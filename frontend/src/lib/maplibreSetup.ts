import maplibregl from "maplibre-gl";
import workerUrl from "maplibre-gl/dist/maplibre-gl-csp-worker.js?url";

let workerConfigured = false;

/** MapLibre needs an explicit worker URL when bundled with Vite. */
export function ensureMapLibreWorker(): void {
  if (workerConfigured) {
    return;
  }

  maplibregl.setWorkerUrl(workerUrl);
  workerConfigured = true;
}
