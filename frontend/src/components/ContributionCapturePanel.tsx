import { useState } from "react";

import { validateImageFile } from "../lib/captureValidation";
import type { LocationPinResponse } from "../lib/types";

type ContributionCapturePanelProps = {
  pin: LocationPinResponse;
  isSubmitting: boolean;
  error: string;
  onSubmit: (image: File) => void;
  onCancel: () => void;
};

function ContributionCapturePanel({
  pin,
  isSubmitting,
  error,
  onSubmit,
  onCancel,
}: ContributionCapturePanelProps) {
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [validationError, setValidationError] = useState("");

  const handleSubmit = () => {
    const message = validateImageFile(imageFile);
    if (message) {
      setValidationError(message);
      return;
    }

    setValidationError("");
    onSubmit(imageFile as File);
  };

  const shownError = validationError || error;

  return (
    <div className="pointer-events-auto absolute bottom-4 left-4 right-4 z-20 mx-auto max-w-lg rounded-lg bg-white p-5 shadow-lg sm:left-auto sm:right-4">
      <h2 className="text-lg font-semibold text-gray-900">Capture a photo</h2>
      <p className="mt-1 text-sm text-gray-600">
        Pin created for building #{pin.osm_building_id}. Upload one clear photo
        and we&apos;ll generate a 3D model of it.
      </p>

      <label className="mt-4 block rounded-md border border-dashed border-gray-300 p-3 text-sm">
        <span className="font-medium text-gray-900">Storefront photo</span>
        <input
          type="file"
          accept="image/jpeg,image/png,image/webp"
          capture="environment"
          disabled={isSubmitting}
          className="mt-2 block w-full text-sm text-gray-600"
          onChange={(event) => {
            setImageFile(event.target.files?.[0] ?? null);
            setValidationError("");
          }}
        />
        {imageFile && (
          <span className="mt-1 block text-xs text-gray-500">
            {imageFile.name}
          </span>
        )}
      </label>

      <p className="mt-2 text-xs text-gray-500">
        Tip: capture the clearest, most central angle of the storefront for the
        best 3D result. JPEG, PNG, or WebP, max 10 MB.
      </p>

      {shownError && <p className="mt-3 text-sm text-red-600">{shownError}</p>}

      <div className="mt-4 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={handleSubmit}
          disabled={isSubmitting || !imageFile}
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isSubmitting ? "Uploading..." : "Generate 3D model"}
        </button>
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
