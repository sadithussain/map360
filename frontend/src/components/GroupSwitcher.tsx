import { type ChangeEvent } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { useApp } from "../context/AppContext";

function GroupSwitcher() {
  const navigate = useNavigate();
  const location = useLocation();
  const {
    groups,
    activeGroupId,
    activeGroup,
    isGroupsLoading,
    switchGroup,
  } = useApp();

  if (groups.length === 0) {
    return null;
  }

  const isSingleGroup = groups.length === 1;
  const isDisabled = isGroupsLoading || isSingleGroup;

  function handleChange(event: ChangeEvent<HTMLSelectElement>) {
    const groupId = event.target.value;
    if (!groupId || groupId === activeGroupId) {
      return;
    }

    switchGroup(groupId);

    if (location.pathname !== "/app") {
      navigate("/app");
    }
  }

  return (
    <label className="flex items-center gap-1.5 text-sm text-gray-600">
      <span className="hidden sm:inline">Group:</span>
      <select
        value={activeGroupId ?? ""}
        onChange={handleChange}
        disabled={isDisabled}
        aria-label="Switch active group"
        className="max-w-[10rem] truncate rounded-md border border-gray-300 bg-white px-2 py-1 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:cursor-default disabled:opacity-70 sm:max-w-[12rem]"
      >
        {groups.map((group) => (
          <option key={group.id} value={group.id}>
            {group.name}
          </option>
        ))}
      </select>
      {isSingleGroup && activeGroup ? (
        <span className="sr-only">{activeGroup.name}</span>
      ) : null}
    </label>
  );
}

export default GroupSwitcher;
