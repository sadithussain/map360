import type { SelectedBuilding } from "../lib/types";

type BuildingSelectionPanelProps = {
  building: SelectedBuilding;
  label: string;
  isSubmitting: boolean;
  error: string;
  onLabelChange: (value: string) => void;
  onContinue: () => void;
  onPickAnother: () => void;
  onCancel: () => void;
};

function BuildingSelectionPanel({
  building,
  label,
  isSubmitting,
  error,
  onLabelChange,
  onContinue,
  onPickAnother,
  onCancel,
}: BuildingSelectionPanelProps) {
  return (
    <div className="pointer-events-auto absolute bottom-4 left-4 right-4 z-20 mx-auto max-w-md rounded-lg bg-white p-5 shadow-lg sm:left-auto sm:right-4">
      <h2 className="text-lg font-semibold text-gray-900">Building selected</h2>
      <p className="mt-1 text-sm text-gray-600">
        {building.osmBuildingId != null
          ? `OSM building #${building.osmBuildingId}`
          : "Building footprint (no OSM id)"}
      </p>
      <p className="mt-1 text-xs text-gray-500">
        {building.centroid.lat.toFixed(5)}, {building.centroid.lng.toFixed(5)}
      </p>

      <label className="mt-4 block text-sm font-medium text-gray-700">
        Label (optional)
        <input
          type="text"
          value={label}
          onChange={(event) => onLabelChange(event.target.value)}
          maxLength={200}
          placeholder="Storefront name"
          className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-900 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
      </label>

      {error && <p className="mt-3 text-sm text-red-600">{error}</p>}

      <div className="mt-4 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={onContinue}
          disabled={isSubmitting}
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isSubmitting ? "Creating pin..." : "Continue to capture"}
        </button>
        <button
          type="button"
          onClick={onPickAnother}
          disabled={isSubmitting}
          className="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-60"
        >
          Pick another building
        </button>
        <button
          type="button"
          onClick={onCancel}
          disabled={isSubmitting}
          className="rounded-md px-4 py-2 text-sm font-medium text-gray-600 transition hover:text-gray-900 disabled:cursor-not-allowed disabled:opacity-60"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

export default BuildingSelectionPanel;
