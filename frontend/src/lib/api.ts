import { clearAuthToken, getAuthHeader } from "./auth";
import type {
  GroupCreate,
  GroupJoinRequest,
  GroupResponse,
  MembershipResponse,
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

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...rest,
    headers: {
      "Content-Type": "application/json",
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
