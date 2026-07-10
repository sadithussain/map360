import { useCallback, useState } from "react";

import BuildingSelectionPanel from "../components/BuildingSelectionPanel";
import ContributionCapturePanel from "../components/ContributionCapturePanel";
import EmptyGroupMapState from "../components/EmptyGroupMapState";
import { WorldMap } from "../components/WorldMap";
import { useApp } from "../context/AppContext";
import { useGroupMapState } from "../hooks/useGroupMapState";
import { ApiError, createLocationPin } from "../lib/api";
import { isEmptyMapState } from "../lib/mapState";
import { setCachedMapState } from "../lib/mapStateCache";
import type {
  ContributionSubmissionDraft,
  LocationPinResponse,
  SelectedBuilding,
} from "../lib/types";

type ContributionStep =
  | "idle"
  | "selecting"
  | "confirming"
  | "capturing"
  | "complete";

function AppShell() {
  const { activeGroupId, activeGroup, user } = useApp();
  const { mapState, isMapStateLoading, mapStateError, refreshMapState } =
    useGroupMapState(activeGroupId);

  const [contributionStep, setContributionStep] =
    useState<ContributionStep>("idle");
  const [selectedBuilding, setSelectedBuilding] =
    useState<SelectedBuilding | null>(null);
  const [pinLabel, setPinLabel] = useState("");
  const [createdPin, setCreatedPin] = useState<LocationPinResponse | null>(null);
  const [selectionError, setSelectionError] = useState("");
  const [isCreatingPin, setIsCreatingPin] = useState(false);
  const [missedClickHint, setMissedClickHint] = useState("");
  const [completedDraft, setCompletedDraft] =
    useState<ContributionSubmissionDraft | null>(null);

  const resetContributionFlow = useCallback(() => {
    setContributionStep("idle");
    setSelectedBuilding(null);
    setPinLabel("");
    setCreatedPin(null);
    setSelectionError("");
    setIsCreatingPin(false);
    setMissedClickHint("");
    setCompletedDraft(null);
  }, []);

  const handleStartContribution = () => {
    resetContributionFlow();
    setContributionStep("selecting");
    setMissedClickHint("Click a building on the map to scan it.");
  };

  const handleBuildingSelect = (building: SelectedBuilding) => {
    setSelectedBuilding(building);
    setContributionStep("confirming");
    setSelectionError("");
    setMissedClickHint("");
  };

  const handleMissedBuildingClick = () => {
    setMissedClickHint(
      "No building found there. Click the building footprint (the base on the ground), or zoom in closer.",
    );
  };

  const handlePickAnotherBuilding = () => {
    setSelectedBuilding(null);
    setSelectionError("");
    setContributionStep("selecting");
    setMissedClickHint("Click a building on the map to scan it.");
  };

  const handleCreatePin = async () => {
    if (!activeGroupId || !selectedBuilding) {
      return;
    }

    if (selectedBuilding.osmBuildingId == null) {
      setSelectionError(
        "This building footprint has no OpenStreetMap id, so it cannot be saved as a pin yet. Please pick another building.",
      );
      return;
    }

    setIsCreatingPin(true);
    setSelectionError("");

    try {
      const pin = await createLocationPin(activeGroupId, {
        osm_building_id: selectedBuilding.osmBuildingId,
        lat: selectedBuilding.centroid.lat,
        lng: selectedBuilding.centroid.lng,
        building_geometry: selectedBuilding.geometry,
        label: pinLabel.trim() || null,
      });

      const refreshed = await refreshMapState();
      if (refreshed) {
        setCachedMapState(activeGroupId, refreshed);
      } else if (mapState) {
        setCachedMapState(activeGroupId, {
          ...mapState,
          pins: [...mapState.pins, pin],
        });
      }

      setCreatedPin(pin);
      setContributionStep("capturing");
    } catch (error: unknown) {
      if (error instanceof ApiError) {
        setSelectionError(error.message);
      } else {
        setSelectionError("Unable to create location pin.");
      }
    } finally {
      setIsCreatingPin(false);
    }
  };

  const handleCaptureComplete = (draft: ContributionSubmissionDraft) => {
    setCompletedDraft(draft);
    setContributionStep("complete");
  };

  if (!activeGroupId) {
    return null;
  }

  const buildingSelectionPhase =
    contributionStep === "selecting"
      ? "choosing"
      : contributionStep === "confirming"
        ? "chosen"
        : "off";

  const showEmptyState =
    !isMapStateLoading &&
    !mapStateError &&
    mapState !== null &&
    isEmptyMapState(mapState) &&
    contributionStep === "idle";

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

      <div className="pointer-events-none absolute inset-x-0 top-3 z-20 flex justify-end px-4">
        {contributionStep === "idle" && (
          <button
            type="button"
            onClick={handleStartContribution}
            className="pointer-events-auto rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-blue-700"
          >
            Add location
          </button>
        )}
      </div>

      {buildingSelectionPhase === "choosing" && (
        <div className="pointer-events-none absolute inset-x-0 top-14 z-20 flex justify-center px-4">
          <p className="rounded-md bg-white/95 px-3 py-1.5 text-sm text-gray-700 shadow-sm">
            {missedClickHint || "Click a building to scan it."}
          </p>
        </div>
      )}

      {contributionStep === "selecting" && (
        <div className="pointer-events-none absolute inset-x-0 bottom-4 z-20 flex justify-center px-4">
          <button
            type="button"
            onClick={resetContributionFlow}
            className="pointer-events-auto rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 shadow-sm transition hover:bg-gray-50"
          >
            Cancel selection
          </button>
        </div>
      )}

      <WorldMap
        variant="workspace"
        mapState={mapState}
        buildingSelectionPhase={buildingSelectionPhase}
        selectedBuilding={selectedBuilding}
        onBuildingSelect={handleBuildingSelect}
        onMissedBuildingClick={handleMissedBuildingClick}
      />

      {showEmptyState && <EmptyGroupMapState groupName={activeGroup?.name} />}

      {contributionStep === "confirming" && selectedBuilding && (
        <BuildingSelectionPanel
          building={selectedBuilding}
          label={pinLabel}
          isSubmitting={isCreatingPin}
          error={selectionError}
          onLabelChange={setPinLabel}
          onContinue={() => void handleCreatePin()}
          onPickAnother={handlePickAnotherBuilding}
          onCancel={resetContributionFlow}
        />
      )}

      {contributionStep === "capturing" && createdPin && user && (
        <ContributionCapturePanel
          pin={createdPin}
          groupId={activeGroupId}
          userId={user.id}
          onComplete={handleCaptureComplete}
          onCancel={resetContributionFlow}
        />
      )}

      {contributionStep === "complete" && completedDraft && (
        <div className="pointer-events-auto absolute bottom-4 left-4 right-4 z-20 mx-auto max-w-md rounded-lg bg-white p-5 shadow-lg sm:left-auto sm:right-4">
          <h2 className="text-lg font-semibold text-gray-900">
            Submission ready
          </h2>
          <p className="mt-2 text-sm text-gray-600">
            {completedDraft.captureMethod === "images"
              ? `${completedDraft.files.length} images`
              : "1 video"}{" "}
            validated for building #{completedDraft.osmBuildingId}. Upload
            wiring arrives in the next stage.
          </p>
          <button
            type="button"
            onClick={resetContributionFlow}
            className="mt-4 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-700"
          >
            Done
          </button>
        </div>
      )}
    </div>
  );
}

export default AppShell;
