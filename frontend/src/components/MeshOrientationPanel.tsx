type MeshOrientationPanelProps = {
  /** Optional human label for the object being adjusted. */
  label?: string | null;
  /** Current heading in degrees (0-360), shown on the slider. */
  heading: number;
  /** Current uniform scale multiplier, shown on the scale slider. */
  scale: number;
  isSaving: boolean;
  error: string;
  onHeadingChange: (heading: number) => void;
  onScaleChange: (scale: number) => void;
  onSave: () => void;
  onCancel: () => void;
};

/** Amount each nudge button rotates the mesh, for touch-precise tweaks. */
const NUDGE_STEP_DEGREES = 15;

/** Bounds and step for the size multiplier. Keep in sync with the backend. */
const MIN_SCALE = 0.25;
const MAX_SCALE = 2.0;
const SCALE_STEP = 0.05;

function normalizeHeading(value: number): number {
  return ((value % 360) + 360) % 360;
}

function clampScale(value: number): number {
  return Math.min(MAX_SCALE, Math.max(MIN_SCALE, value));
}

function MeshOrientationPanel({
  label,
  heading,
  scale,
  isSaving,
  error,
  onHeadingChange,
  onScaleChange,
  onSave,
  onCancel,
}: MeshOrientationPanelProps) {
  const rounded = Math.round(normalizeHeading(heading));
  const clampedScale = clampScale(scale);
  const scalePercent = Math.round(clampedScale * 100);

  return (
    <div className="pointer-events-auto absolute bottom-4 left-4 right-4 z-20 mx-auto max-w-md rounded-lg bg-white p-5 shadow-lg sm:left-auto sm:right-4">
      <h2 className="text-lg font-semibold text-gray-900">Adjust building</h2>
      <p className="mt-1 text-sm text-gray-600">
        {label
          ? `Rotate and resize "${label}" until it fits its plot.`
          : "Rotate and resize the model until it fits its plot."}
      </p>

      <div className="mt-4">
        <div className="flex items-center justify-between text-sm font-medium text-gray-700">
          <span>Rotation</span>
          <span className="tabular-nums text-gray-900">{rounded}°</span>
        </div>
        <input
          type="range"
          min={0}
          max={360}
          step={1}
          value={rounded}
          onChange={(event) => onHeadingChange(Number(event.target.value))}
          className="mt-2 w-full accent-blue-600"
          aria-label="Building rotation in degrees"
        />
        <div className="mt-3 flex items-center justify-center gap-2">
          <button
            type="button"
            onClick={() => onHeadingChange(normalizeHeading(heading - NUDGE_STEP_DEGREES))}
            className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 transition hover:bg-gray-50"
          >
            -{NUDGE_STEP_DEGREES}°
          </button>
          <button
            type="button"
            onClick={() => onHeadingChange(normalizeHeading(heading + NUDGE_STEP_DEGREES))}
            className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 transition hover:bg-gray-50"
          >
            +{NUDGE_STEP_DEGREES}°
          </button>
        </div>
      </div>

      <div className="mt-5">
        <div className="flex items-center justify-between text-sm font-medium text-gray-700">
          <span>Size</span>
          <span className="tabular-nums text-gray-900">{scalePercent}%</span>
        </div>
        <input
          type="range"
          min={MIN_SCALE}
          max={MAX_SCALE}
          step={SCALE_STEP}
          value={clampedScale}
          onChange={(event) => onScaleChange(Number(event.target.value))}
          className="mt-2 w-full accent-blue-600"
          aria-label="Building size multiplier"
        />
        <div className="mt-3 flex items-center justify-center gap-2">
          <button
            type="button"
            onClick={() => onScaleChange(clampScale(clampedScale - SCALE_STEP))}
            className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 transition hover:bg-gray-50"
          >
            Smaller
          </button>
          <button
            type="button"
            onClick={() => onScaleChange(clampScale(clampedScale + SCALE_STEP))}
            className="rounded-md border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-700 transition hover:bg-gray-50"
          >
            Larger
          </button>
        </div>
      </div>

      {error && <p className="mt-3 text-sm text-red-600">{error}</p>}

      <div className="mt-4 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={onSave}
          disabled={isSaving}
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isSaving ? "Saving…" : "Save changes"}
        </button>
        <button
          type="button"
          onClick={onCancel}
          disabled={isSaving}
          className="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-60"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

export default MeshOrientationPanel;
