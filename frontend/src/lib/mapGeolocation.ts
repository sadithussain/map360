export type MapView = {
  lng: number;
  lat: number;
  zoom: number;
};

export const FALLBACK_MAP_VIEW: MapView = {
  lng: -73.9857,
  lat: 40.7484,
  zoom: 16,
};

const GEOLOCATION_TIMEOUT_MS = 5000;

function getCurrentPosition(): Promise<GeolocationPosition> {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error("Geolocation is not supported"));
      return;
    }

    navigator.geolocation.getCurrentPosition(resolve, reject, {
      enableHighAccuracy: false,
      timeout: GEOLOCATION_TIMEOUT_MS,
      maximumAge: 60_000,
    });
  });
}

export async function getInitialMapView(): Promise<MapView> {
  try {
    const position = await getCurrentPosition();
    return {
      lng: position.coords.longitude,
      lat: position.coords.latitude,
      zoom: 16,
    };
  } catch {
    return FALLBACK_MAP_VIEW;
  }
}
