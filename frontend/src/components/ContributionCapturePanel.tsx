import { useState } from "react";

import {
  MAX_VIDEO_DURATION_SECONDS,
  REQUIRED_IMAGE_COUNT,
  validateImageFiles,
  validateVideoDuration,
  validateVideoFile,
} from "../lib/captureValidation";
import type {
  CaptureMethod,
  ContributionSubmissionDraft,
  LocationPinResponse,
} from "../lib/types";

const IMAGE_SLOTS = [
  { key: "left", label: "Left angle" },
  { key: "center", label: "Center angle" },
  { key: "right", label: "Right angle" },
] as const;

type ContributionCapturePanelProps = {
  pin: LocationPinResponse;
  groupId: string;
  userId: string;
  onComplete: (draft: ContributionSubmissionDraft) => void;
  onCancel: () => void;
};

function ContributionCapturePanel({
  pin,
  groupId,
  userId,
  onComplete,
  onCancel,
}: ContributionCapturePanelProps) {
  const [captureMethod, setCaptureMethod] = useState<CaptureMethod | null>(null);
  const [imageFiles, setImageFiles] = useState<Array<File | null>>([
    null,
    null,
    null,
  ]);
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleImageChange = (index: number, file: File | null) => {
    setImageFiles((current) => {
      const next = [...current];
      next[index] = file;
      return next;
    });
    setError("");
  };

  const handleSubmit = async () => {
    if (!captureMethod) {
      setError("Choose a capture method.");
      return;
    }

    setIsSubmitting(true);
    setError("");

    try {
      if (captureMethod === "images") {
        const files = imageFiles.filter((file): file is File => file !== null);
        const validationError = validateImageFiles(files);
        if (validationError) {
          setError(validationError);
          return;
        }

        onComplete({
          pinId: pin.id,
          groupId,
          userId,
          osmBuildingId: pin.osm_building_id,
          lat: pin.lat,
          lng: pin.lng,
          captureMethod,
          files,
        });
        return;
      }

      const validationError = validateVideoFile(videoFile);
      if (validationError) {
        setError(validationError);
        return;
      }

      const durationError = await validateVideoDuration(videoFile as File);
      if (durationError) {
        setError(durationError);
        return;
      }

      onComplete({
        pinId: pin.id,
        groupId,
        userId,
        osmBuildingId: pin.osm_building_id,
        lat: pin.lat,
        lng: pin.lng,
        captureMethod,
        files: [videoFile as File],
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="pointer-events-auto absolute bottom-4 left-4 right-4 z-20 mx-auto max-w-lg rounded-lg bg-white p-5 shadow-lg sm:left-auto sm:right-4">
      <h2 className="text-lg font-semibold text-gray-900">Capture media</h2>
      <p className="mt-1 text-sm text-gray-600">
        Pin created for building #{pin.osm_building_id}. Choose how you want to
        scan this location.
      </p>

      {!captureMethod ? (
        <div className="mt-4 grid gap-2 sm:grid-cols-2">
          <button
            type="button"
            onClick={() => setCaptureMethod("images")}
            className="rounded-md border border-gray-300 bg-white px-4 py-3 text-left text-sm transition hover:border-blue-500 hover:bg-blue-50"
          >
            <span className="block font-medium text-gray-900">3 images</span>
            <span className="mt-1 block text-gray-600">
              Left, center, and right angles
            </span>
          </button>
          <button
            type="button"
            onClick={() => setCaptureMethod("video")}
            className="rounded-md border border-gray-300 bg-white px-4 py-3 text-left text-sm transition hover:border-blue-500 hover:bg-blue-50"
          >
            <span className="block font-medium text-gray-900">Short video</span>
            <span className="mt-1 block text-gray-600">
              ~{MAX_VIDEO_DURATION_SECONDS}s horizontal sweep
            </span>
          </button>
        </div>
      ) : captureMethod === "images" ? (
        <div className="mt-4 space-y-3">
          {IMAGE_SLOTS.map((slot, index) => (
            <label
              key={slot.key}
              className="block rounded-md border border-dashed border-gray-300 p-3 text-sm"
            >
              <span className="font-medium text-gray-900">{slot.label}</span>
              <input
                type="file"
                accept="image/jpeg,image/png,image/webp"
                className="mt-2 block w-full text-sm text-gray-600"
                onChange={(event) =>
                  handleImageChange(index, event.target.files?.[0] ?? null)
                }
              />
              {imageFiles[index] && (
                <span className="mt-1 block text-xs text-gray-500">
                  {imageFiles[index]?.name}
                </span>
              )}
            </label>
          ))}
          <p className="text-xs text-gray-500">
            Provide exactly {REQUIRED_IMAGE_COUNT} images (JPEG, PNG, or WebP, max
            10 MB each).
          </p>
        </div>
      ) : (
        <div className="mt-4">
          <label className="block rounded-md border border-dashed border-gray-300 p-3 text-sm">
            <span className="font-medium text-gray-900">Horizontal video sweep</span>
            <input
              type="file"
              accept="video/mp4,video/webm"
              className="mt-2 block w-full text-sm text-gray-600"
              onChange={(event) => {
                setVideoFile(event.target.files?.[0] ?? null);
                setError("");
              }}
            />
            {videoFile && (
              <span className="mt-1 block text-xs text-gray-500">
                {videoFile.name}
              </span>
            )}
          </label>
          <p className="mt-2 text-xs text-gray-500">
            MP4 or WebM, max {MAX_VIDEO_DURATION_SECONDS} seconds and 50 MB.
          </p>
        </div>
      )}

      {error && <p className="mt-3 text-sm text-red-600">{error}</p>}

      <div className="mt-4 flex flex-wrap gap-2">
        {captureMethod && (
          <button
            type="button"
            onClick={handleSubmit}
            disabled={isSubmitting}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isSubmitting ? "Validating..." : "Prepare submission"}
          </button>
        )}
        {captureMethod && (
          <button
            type="button"
            onClick={() => {
              setCaptureMethod(null);
              setImageFiles([null, null, null]);
              setVideoFile(null);
              setError("");
            }}
            disabled={isSubmitting}
            className="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50"
          >
            Change method
          </button>
        )}
        <button
          type="button"
          onClick={onCancel}
          disabled={isSubmitting}
          className="rounded-md px-4 py-2 text-sm font-medium text-gray-600 transition hover:text-gray-900"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

export default ContributionCapturePanel;
