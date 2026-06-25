import EmptyGroupMapState from "../components/EmptyGroupMapState";
import { WorldMap } from "../components/WorldMap";
import { useApp } from "../context/AppContext";
import { useGroupMapState } from "../hooks/useGroupMapState";
import { isEmptyMapState } from "../lib/mapState";

function AppShell() {
  const { activeGroupId, activeGroup } = useApp();
  const { mapState, isMapStateLoading, mapStateError } =
    useGroupMapState(activeGroupId);

  if (!activeGroupId) {
    return null;
  }

  return (
    <div className="relative h-full min-h-0">
      {(isMapStateLoading || mapStateError) && (
        <div className="pointer-events-none absolute inset-x-0 top-3 z-10 flex justify-center px-4">
          <p
            className={`rounded-md px-3 py-1.5 text-sm shadow-sm ${
              mapStateError
                ? "bg-red-50 text-red-700"
                : "bg-white/90 text-gray-700"
            }`}
          >
            {mapStateError || `Loading ${activeGroup?.name ?? "group"} map...`}
          </p>
        </div>
      )}

      <WorldMap variant="workspace" mapState={mapState} />

      {!isMapStateLoading &&
        !mapStateError &&
        mapState !== null &&
        isEmptyMapState(mapState) && (
          <EmptyGroupMapState groupName={activeGroup?.name} />
        )}
    </div>
  );
}

export default AppShell;
