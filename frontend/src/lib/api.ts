import { clearAuthToken, getAuthHeader } from "./auth";
import type {
  GroupCreate,
  GroupJoinRequest,
  GroupResponse,
  LocationPinCreate,
  LocationPinResponse,
  MapObjectResponse,
  MapStateResponse,
  MembershipResponse,
  SubmissionResponse,
  Token,
  UserCreate,
  UserLogin,
  UserResponse,
} from "./types";

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export class UnauthorizedError extends ApiError {
  constructor(message = "Could not validate credentials.") {
    super(message, 401);
    this.name = "UnauthorizedError";
  }
}

type ApiFetchOptions = RequestInit & {
  /** When false, do not attach the Bearer token (e.g. login/register). */
  auth?: boolean;
};

async function parseErrorDetail(response: Response): Promise<string> {
  try {
    const body: { detail?: string } = await response.json();
    if (typeof body.detail === "string" && body.detail.length > 0) {
      return body.detail;
    }
  } catch {
    // ignore JSON parse failures
  }
  return `Request failed (${response.status})`;
}

export async function apiFetch<T>(
  path: string,
  options: ApiFetchOptions = {},
): Promise<T> {
  const { auth = true, headers, ...rest } = options;

  // Let the browser set the multipart boundary for FormData bodies; forcing
  // application/json would corrupt file uploads.
  const isFormData = rest.body instanceof FormData;

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...rest,
    headers: {
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
      ...(auth ? getAuthHeader() : {}),
      ...headers,
    },
  });

  if (response.status === 401 && auth) {
    clearAuthToken();
    throw new UnauthorizedError(await parseErrorDetail(response));
  }

  if (!response.ok) {
    throw new ApiError(await parseErrorDetail(response), response.status);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export function login(credentials: UserLogin): Promise<Token> {
  return apiFetch<Token>("/users/login", {
    method: "POST",
    auth: false,
    body: JSON.stringify(credentials),
  });
}

export function register(user: UserCreate): Promise<UserResponse> {
  return apiFetch<UserResponse>("/users/register", {
    method: "POST",
    auth: false,
    body: JSON.stringify(user),
  });
}

export function getCurrentUser(): Promise<UserResponse> {
  return apiFetch<UserResponse>("/users/me");
}

export async function checkEmailExists(email: string): Promise<boolean> {
  return apiFetch<boolean>(
    `/users/exists/email/${encodeURIComponent(email)}`,
    { auth: false },
  );
}

export async function checkUsernameExists(username: string): Promise<boolean> {
  return apiFetch<boolean>(
    `/users/exists/username/${encodeURIComponent(username)}`,
    { auth: false },
  );
}

export function listMyGroups(): Promise<GroupResponse[]> {
  return apiFetch<GroupResponse[]>("/groups/me");
}

export function createGroup(payload: GroupCreate): Promise<GroupResponse> {
  return apiFetch<GroupResponse>("/groups/create", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function joinGroup(payload: GroupJoinRequest): Promise<MembershipResponse> {
  return apiFetch<MembershipResponse>("/groups/join", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getGroupMapState(groupId: string): Promise<MapStateResponse> {
  return apiFetch<MapStateResponse>(`/groups/${groupId}/map-state`);
}

/** Optional lng/lat bounding box for {@link listMapObjects}. */
export type MapObjectsBbox = {
  minLng: number;
  minLat: number;
  maxLng: number;
  maxLat: number;
};

/** List a group's generated map objects, optionally within a bounding box. */
export function listMapObjects(
  groupId: string,
  bbox?: MapObjectsBbox,
): Promise<MapObjectResponse[]> {
  const query = bbox
    ? `?${new URLSearchParams({
        min_lng: String(bbox.minLng),
        min_lat: String(bbox.minLat),
        max_lng: String(bbox.maxLng),
        max_lat: String(bbox.maxLat),
      }).toString()}`
    : "";
  return apiFetch<MapObjectResponse[]>(`/groups/${groupId}/map-objects${query}`);
}

/** Fetch a single map object (with its mesh URL) from a group. */
export function getMapObject(
  groupId: string,
  objectId: string,
): Promise<MapObjectResponse> {
  return apiFetch<MapObjectResponse>(
    `/groups/${groupId}/map-objects/${objectId}`,
  );
}

/**
 * Adjust a placed map object's transform: yaw ``heading`` (degrees clockwise
 * from north) and uniform ``scale`` multiplier. Any group member may adjust it.
 */
export function updateMapObjectTransform(
  groupId: string,
  objectId: string,
  heading: number,
  scale: number,
): Promise<MapObjectResponse> {
  return apiFetch<MapObjectResponse>(
    `/groups/${groupId}/map-objects/${objectId}`,
    {
      method: "PATCH",
      body: JSON.stringify({ heading, scale }),
    },
  );
}

export function createLocationPin(
  groupId: string,
  payload: LocationPinCreate,
): Promise<LocationPinResponse> {
  return apiFetch<LocationPinResponse>(`/groups/${groupId}/pins`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/** Delete a location pin (and its submissions/objects) from a group. */
export function deleteLocationPin(
  groupId: string,
  pinId: string,
): Promise<void> {
  return apiFetch<void>(`/groups/${groupId}/pins/${pinId}`, {
    method: "DELETE",
  });
}

/** Delete every location pin in a group (cascades submissions/objects). */
export function deleteAllLocationPins(
  groupId: string,
): Promise<{ deleted: number }> {
  return apiFetch<{ deleted: number }>(`/groups/${groupId}/pins`, {
    method: "DELETE",
  });
}

/** Upload one photo and start async TRELLIS mesh generation for a pin. */
export function createGeneration(
  groupId: string,
  pinId: string,
  image: File,
): Promise<SubmissionResponse> {
  const formData = new FormData();
  formData.append("image", image);
  return apiFetch<SubmissionResponse>(
    `/groups/${groupId}/pins/${pinId}/generations`,
    {
      method: "POST",
      body: formData,
    },
  );
}

/** Poll the status of a generation submission. */
export function getGeneration(
  groupId: string,
  generationId: string,
): Promise<SubmissionResponse> {
  return apiFetch<SubmissionResponse>(
    `/groups/${groupId}/generations/${generationId}`,
  );
}

/** List all generation submissions for a pin (newest first). */
export function listPinGenerations(
  groupId: string,
  pinId: string,
): Promise<SubmissionResponse[]> {
  return apiFetch<SubmissionResponse[]>(
    `/groups/${groupId}/pins/${pinId}/generations`,
  );
}

/** List all generation submissions for a group (newest first). */
export function listGroupGenerations(
  groupId: string,
): Promise<SubmissionResponse[]> {
  return apiFetch<SubmissionResponse[]>(`/groups/${groupId}/generations`);
}
