import { useCallback, useEffect, useState } from "react";

import { ApiError, getGroupMapState } from "../lib/api";
import {
  getCachedMapState,
  setCachedMapState,
} from "../lib/mapStateCache";
import type { MapStateResponse } from "../lib/types";

type UseGroupMapStateResult = {
  mapState: MapStateResponse | null;
  isMapStateLoading: boolean;
  mapStateError: string;
  refreshMapState: () => Promise<MapStateResponse | null>;
};

// How often the active group's map state is silently re-fetched so members see
// meshes contributed by others without a manual refresh.
const MAP_STATE_POLL_INTERVAL_MS = 20_000;

export function useGroupMapState(
  activeGroupId: string | null,
): UseGroupMapStateResult {
  const [mapState, setMapState] = useState<MapStateResponse | null>(null);
  const [isMapStateLoading, setIsMapStateLoading] = useState(false);
  const [mapStateError, setMapStateError] = useState("");

  const refreshMapState = useCallback(async (): Promise<MapStateResponse | null> => {
    if (!activeGroupId) {
      return null;
    }

    setIsMapStateLoading(true);
    setMapStateError("");

    try {
      const state = await getGroupMapState(activeGroupId);
      setCachedMapState(activeGroupId, state);
      setMapState(state);
      return state;
    } catch (error: unknown) {
      setMapState(null);
      if (error instanceof ApiError) {
        setMapStateError(error.message);
      } else {
        setMapStateError("Unable to load map state.");
      }
      return null;
    } finally {
      setIsMapStateLoading(false);
    }
  }, [activeGroupId]);

  useEffect(() => {
    if (!activeGroupId) {
      setMapState(null);
      setIsMapStateLoading(false);
      setMapStateError("");
      return;
    }

    let cancelled = false;
    const cached = getCachedMapState(activeGroupId);
    const hadCache = cached !== undefined;

    if (hadCache) {
      setMapState(cached);
      setIsMapStateLoading(false);
      setMapStateError("");
    } else {
      setMapState(null);
      setIsMapStateLoading(true);
      setMapStateError("");
    }

    void getGroupMapState(activeGroupId)
      .then((state) => {
        if (cancelled) {
          return;
        }

        setCachedMapState(activeGroupId, state);
        setMapState(state);
        setMapStateError("");
      })
      .catch((error: unknown) => {
        if (cancelled) {
          return;
        }

        if (hadCache) {
          return;
        }

        setMapState(null);
        if (error instanceof ApiError) {
          setMapStateError(error.message);
        } else {
          setMapStateError("Unable to load map state.");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsMapStateLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [activeGroupId]);

  // Poll the active group's map state so newly contributed meshes appear for
  // every member. This is a silent refresh: it never toggles the loading state
  // or clears the map on transient errors, so the current view stays stable.
  useEffect(() => {
    if (!activeGroupId) {
      return;
    }

    let cancelled = false;
    const interval = window.setInterval(() => {
      void getGroupMapState(activeGroupId)
        .then((state) => {
          if (cancelled) {
            return;
          }
          setCachedMapState(activeGroupId, state);
          setMapState(state);
          setMapStateError("");
        })
        .catch(() => {
          // Keep the last good state; the next poll will retry.
        });
    }, MAP_STATE_POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [activeGroupId]);

  return { mapState, isMapStateLoading, mapStateError, refreshMapState };
}
