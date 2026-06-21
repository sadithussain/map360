import { useApp } from "../context/AppContext";
import { WorldMap } from "../components/WorldMap";

function AppShell() {
  const { activeGroupId } = useApp();

  if (!activeGroupId) {
    return null;
  }

  return (
    <div className="h-full min-h-0">
      <WorldMap key={activeGroupId} variant="workspace" />
    </div>
  );
}

export default AppShell;
