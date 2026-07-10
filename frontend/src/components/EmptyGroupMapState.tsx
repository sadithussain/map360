type EmptyGroupMapStateProps = {
  groupName?: string | null;
};

function EmptyGroupMapState({ groupName }: EmptyGroupMapStateProps) {
  const displayName = groupName?.trim() || "This group";

  return (
    <div className="pointer-events-none absolute inset-0 flex items-center justify-center px-4">
      <div className="max-w-md rounded-lg bg-white/90 px-6 py-5 text-center shadow-sm">
        <h2 className="text-lg font-semibold text-gray-900">
          No contributions yet
        </h2>
        <p className="mt-2 text-sm text-gray-600">
          {displayName} doesn&apos;t have any mapped locations yet. Use{" "}
          <span className="font-medium">Add location</span> to select a building
          and start your first scan.
        </p>
      </div>
    </div>
  );
}

export default EmptyGroupMapState;
