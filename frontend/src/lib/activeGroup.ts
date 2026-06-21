// Client-side persistence for the user's currently selected group.
// No backend endpoint exists yet; this is used until group-scoped map APIs land.

const ACTIVE_GROUP_KEY = "map360.active_group_id";
const ACTIVE_GROUP_CHANGE_EVENT = "map360:active-group-change";

export function getActiveGroupId(): string | null {
  return localStorage.getItem(ACTIVE_GROUP_KEY);
}

export function setActiveGroupId(groupId: string) {
  localStorage.setItem(ACTIVE_GROUP_KEY, groupId);
  window.dispatchEvent(new Event(ACTIVE_GROUP_CHANGE_EVENT));
}

export function clearActiveGroupId() {
  localStorage.removeItem(ACTIVE_GROUP_KEY);
  window.dispatchEvent(new Event(ACTIVE_GROUP_CHANGE_EVENT));
}

export function onActiveGroupChange(listener: () => void): () => void {
  const handleStorage = (event: StorageEvent) => {
    if (event.key === ACTIVE_GROUP_KEY) {
      listener();
    }
  };
  window.addEventListener(ACTIVE_GROUP_CHANGE_EVENT, listener);
  window.addEventListener("storage", handleStorage);
  return () => {
    window.removeEventListener(ACTIVE_GROUP_CHANGE_EVENT, listener);
    window.removeEventListener("storage", handleStorage);
  };
}
