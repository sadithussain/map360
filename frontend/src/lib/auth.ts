// Lightweight client-side auth token storage.
// The backend issues a JWT from POST /users/login; we persist it in
// localStorage so the session survives a page refresh.

const TOKEN_KEY = "map360.access_token";
const TOKEN_TYPE_KEY = "map360.token_type";

// Notify listeners (e.g. App) when auth state changes within the same tab,
// since the native "storage" event only fires across tabs.
const AUTH_CHANGE_EVENT = "map360:auth-change";

export function saveAuthToken(accessToken: string, tokenType = "bearer") {
  localStorage.setItem(TOKEN_KEY, accessToken);
  localStorage.setItem(TOKEN_TYPE_KEY, tokenType);
  window.dispatchEvent(new Event(AUTH_CHANGE_EVENT));
}

export function getAuthToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function clearAuthToken() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(TOKEN_TYPE_KEY);
  window.dispatchEvent(new Event(AUTH_CHANGE_EVENT));
}

export function isLoggedIn(): boolean {
  return getAuthToken() !== null;
}

// Build the Authorization header for authenticated requests. Returns an empty
// object when no token is stored so it can be spread into fetch headers safely.
export function getAuthHeader(): Record<string, string> {
  const token = getAuthToken();
  if (!token) {
    return {};
  }
  const tokenType = localStorage.getItem(TOKEN_TYPE_KEY) || "bearer";
  const scheme = tokenType.charAt(0).toUpperCase() + tokenType.slice(1);
  return { Authorization: `${scheme} ${token}` };
}

// Subscribe to auth changes from this tab and others. Returns an unsubscribe fn.
export function onAuthChange(listener: () => void): () => void {
  const handleStorage = (event: StorageEvent) => {
    if (event.key === TOKEN_KEY) {
      listener();
    }
  };
  window.addEventListener(AUTH_CHANGE_EVENT, listener);
  window.addEventListener("storage", handleStorage);
  return () => {
    window.removeEventListener(AUTH_CHANGE_EVENT, listener);
    window.removeEventListener("storage", handleStorage);
  };
}
