import type { MapStateResponse } from "./types";

const cache = new Map<string, MapStateResponse>();

export function getCachedMapState(
  groupId: string,
): MapStateResponse | undefined {
  return cache.get(groupId);
}

export function setCachedMapState(
  groupId: string,
  state: MapStateResponse,
): void {
  cache.set(groupId, state);
}

export function invalidateMapStateCache(groupId?: string): void {
  if (groupId === undefined) {
    cache.clear();
    return;
  }

  cache.delete(groupId);
}

export function pruneMapStateCache(validGroupIds: string[]): void {
  const valid = new Set(validGroupIds);
  for (const groupId of cache.keys()) {
    if (!valid.has(groupId)) {
      cache.delete(groupId);
    }
  }
}
