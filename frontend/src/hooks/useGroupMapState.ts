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

  return { mapState, isMapStateLoading, mapStateError, refreshMapState };
}
