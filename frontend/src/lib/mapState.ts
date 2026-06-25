import type { LocationPinResponse, MapStateResponse } from "./types";

export function isEmptyMapState(state: MapStateResponse): boolean {
  return state.pins.length === 0 && state.objects.length === 0;
}

export function pinsBounds(
  pins: LocationPinResponse[],
): [[number, number], [number, number]] | null {
  if (pins.length === 0) {
    return null;
  }

  let minLng = pins[0].lng;
  let maxLng = pins[0].lng;
  let minLat = pins[0].lat;
  let maxLat = pins[0].lat;

  for (const pin of pins) {
    minLng = Math.min(minLng, pin.lng);
    maxLng = Math.max(maxLng, pin.lng);
    minLat = Math.min(minLat, pin.lat);
    maxLat = Math.max(maxLat, pin.lat);
  }

  return [
    [minLng, minLat],
    [maxLng, maxLat],
  ];
}
