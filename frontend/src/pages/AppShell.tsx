import { useCallback, useEffect, useState } from "react";

import BuildingSelectionPanel from "../components/BuildingSelectionPanel";
import ContributionCapturePanel from "../components/ContributionCapturePanel";
import EmptyGroupMapState from "../components/EmptyGroupMapState";
import { WorldMap } from "../components/WorldMap";
import { useApp } from "../context/AppContext";
import { useGroupMapState } from "../hooks/useGroupMapState";
import {
  ApiError,
  createGeneration,
  createLocationPin,
  deleteLocationPin,
  getGeneration,
} from "../lib/api";
import { isEmptyMapState } from "../lib/mapState";
import { setCachedMapState } from "../lib/mapStateCache";
import type {
  LocationPinResponse,
  SelectedBuilding,
  SubmissionResponse,
} from "../lib/types";

const GENERATION_POLL_INTERVAL_MS = 10_000;

type ContributionStep =
  | "idle"
  | "selecting"
  | "confirming"
  | "capturing"
  | "processing"
  | "ready"
  | "failed";

function AppShell() {
  const { activeGroupId, activeGroup } = useApp();
  const { mapState, isMapStateLoading, mapStateError, refreshMapState } =
    useGroupMapState(activeGroupId);

  const [contributionStep, setContributionStep] =
    useState<ContributionStep>("idle");
  const [selectedBuilding, setSelectedBuilding] =
    useState<SelectedBuilding | null>(null);
  const [pinLabel, setPinLabel] = useState("");
  const [selectionError, setSelectionError] = useState("");
  const [missedClickHint, setMissedClickHint] = useState("");
  const [submission, setSubmission] = useState<SubmissionResponse | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");

  const resetContributionFlow = useCallback(() => {
    setContributionStep("idle");
    setSelectedBuilding(null);
    setPinLabel("");
    setSelectionError("");
    setMissedClickHint("");
    setSubmission(null);
    setIsUploading(false);
    setUploadError("");
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

  const handleContinueToCapture = () => {
    if (!selectedBuilding) {
      return;
    }

    if (selectedBuilding.osmBuildingId == null) {
      setSelectionError(
        "This building footprint has no OpenStreetMap id, so it cannot be saved as a pin yet. Please pick another building.",
      );
      return;
    }

    setSelectionError("");
    setContributionStep("capturing");
  };

  const handleCaptureSubmit = async (image: File) => {
    if (
      !activeGroupId ||
      !selectedBuilding ||
      selectedBuilding.osmBuildingId == null
    ) {
      return;
    }

    setIsUploading(true);
    setUploadError("");

    // The pin is created only now, alongside the upload, so canceling before
    // this point never leaves an empty pin behind.
    let pin: LocationPinResponse;
    try {
      pin = await createLocationPin(activeGroupId, {
        osm_building_id: selectedBuilding.osmBuildingId,
        lat: selectedBuilding.centroid.lat,
        lng: selectedBuilding.centroid.lng,
        building_geometry: selectedBuilding.geometry,
        label: pinLabel.trim() || null,
      });
    } catch (error: unknown) {
      setUploadError(
        error instanceof ApiError
          ? error.message
          : "Unable to create location pin.",
      );
      setIsUploading(false);
      return;
    }

    try {
      const created = await createGeneration(activeGroupId, pin.id, image);
      setSubmission(created);
      setContributionStep("processing");
    } catch (error: unknown) {
      // Roll back the just-created pin so a failed upload leaves nothing.
      try {
        await deleteLocationPin(activeGroupId, pin.id);
      } catch {
        // Best-effort cleanup; the backend also prunes orphan pins.
      }
      if (error instanceof ApiError) {
        setUploadError(error.message);
      } else {
        setUploadError("Unable to start 3D generation.");
      }
    } finally {
      setIsUploading(false);
    }
  };

  useEffect(() => {
    if (
      contributionStep !== "processing" ||
      !activeGroupId ||
      submission === null
    ) {
      return;
    }

    let cancelled = false;
    const submissionId = submission.id;

    const poll = async () => {
      try {
        const latest = await getGeneration(activeGroupId, submissionId);
        if (cancelled) {
          return;
        }

        if (latest.status === "ready") {
          setSubmission(latest);
          setContributionStep("ready");
          const refreshed = await refreshMapState();
          if (!cancelled && refreshed) {
            setCachedMapState(activeGroupId, refreshed);
          }
        } else if (latest.status === "failed") {
          setSubmission(latest);
          setContributionStep("failed");
          // The render failed, so the pin has no 3D model; remove it (the
          // error message is already captured in `latest` for display).
          try {
            await deleteLocationPin(activeGroupId, latest.pin_id);
          } catch {
            // Best-effort cleanup; the orphan stays hidden from the map.
          }
        }
      } catch {
        // Transient errors (e.g. Colab waking up) are ignored; keep polling.
      }
    };

    const interval = window.setInterval(poll, GENERATION_POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [contributionStep, activeGroupId, submission, refreshMapState]);

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
          error={selectionError}
          onLabelChange={setPinLabel}
          onContinue={handleContinueToCapture}
          onPickAnother={handlePickAnotherBuilding}
          onCancel={resetContributionFlow}
        />
      )}

      {contributionStep === "capturing" && selectedBuilding && (
        <ContributionCapturePanel
          building={selectedBuilding}
          isSubmitting={isUploading}
          error={uploadError}
          onSubmit={(image) => void handleCaptureSubmit(image)}
          onCancel={resetContributionFlow}
        />
      )}

      {contributionStep === "processing" && (
        <div className="pointer-events-auto absolute bottom-4 left-4 right-4 z-20 mx-auto max-w-md rounded-lg bg-white p-5 shadow-lg sm:left-auto sm:right-4">
          <h2 className="text-lg font-semibold text-gray-900">
            Generating 3D model
          </h2>
          <p className="mt-2 text-sm text-gray-600">
            Your photo is being turned into a 3D model. This can take a few
            minutes &mdash; you can keep exploring the map and it will appear
            here when it&apos;s ready.
          </p>
          <button
            type="button"
            onClick={resetContributionFlow}
            className="mt-4 rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50"
          >
            Continue exploring
          </button>
        </div>
      )}

      {contributionStep === "ready" && (
        <div className="pointer-events-auto absolute bottom-4 left-4 right-4 z-20 mx-auto max-w-md rounded-lg bg-white p-5 shadow-lg sm:left-auto sm:right-4">
          <h2 className="text-lg font-semibold text-gray-900">
            3D model ready
          </h2>
          <p className="mt-2 text-sm text-gray-600">
            Your generated model has been added to the group map.
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

      {contributionStep === "failed" && (
        <div className="pointer-events-auto absolute bottom-4 left-4 right-4 z-20 mx-auto max-w-md rounded-lg bg-white p-5 shadow-lg sm:left-auto sm:right-4">
          <h2 className="text-lg font-semibold text-gray-900">
            Generation failed
          </h2>
          <p className="mt-2 text-sm text-gray-600">
            {submission?.error_message ||
              "Something went wrong while generating the 3D model. Please try again."}
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            {selectedBuilding && (
              <button
                type="button"
                onClick={() => {
                  setSubmission(null);
                  setUploadError("");
                  setContributionStep("capturing");
                }}
                className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-700"
              >
                Try again
              </button>
            )}
            <button
              type="button"
              onClick={resetContributionFlow}
              className="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50"
            >
              Done
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default AppShell;
