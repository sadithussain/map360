import { Link } from "react-router-dom";
import { useApp } from "../context/AppContext";

function AppShell() {
  const { activeGroup, logout } = useApp();

  if (!activeGroup) {
    return null;
  }

  return (
    <div className="flex h-full flex-col bg-gray-100">
      <div className="border-b border-gray-200 bg-white px-6 py-8 shadow-sm">
        <p className="text-sm font-medium uppercase tracking-wide text-blue-600">
          Group workspace
        </p>
        <h1 className="mt-1 text-3xl font-bold">{activeGroup.name}</h1>
        <p className="mt-2 text-gray-600">Your group workspace</p>
      </div>

      <div className="flex flex-1 flex-col items-center justify-center gap-6 px-6 py-12">
        <div className="max-w-lg rounded-xl border border-dashed border-gray-300 bg-white p-10 text-center shadow-sm">
          <p className="text-lg text-gray-700">
            3D map and contributions are coming in the next stage.
          </p>
          <p className="mt-2 text-sm text-gray-500">
            You&apos;ve selected a group. Map loading and group-scoped world state
            will be wired up here soon.
          </p>
        </div>

        <div className="flex flex-wrap items-center justify-center gap-4">
          <Link
            to="/groups"
            className="rounded-md border border-gray-300 bg-white px-5 py-2 font-medium text-gray-800 transition hover:bg-gray-50"
          >
            Switch group
          </Link>
          <button
            type="button"
            onClick={logout}
            className="rounded-md bg-gray-800 px-5 py-2 font-medium text-white transition hover:bg-gray-900"
          >
            Logout
          </button>
        </div>
      </div>
    </div>
  );
}

export default AppShell;
