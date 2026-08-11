/** API response shapes mirrored from the backend Pydantic schemas. */

import type { MultiPolygon, Polygon } from "geojson";

export type UserResponse = {
  id: string;
  username: string;
  email: string;
  experience_points: number;
  created_at: string;
};

export type Token = {
  access_token: string;
  token_type: string;
};

export type GroupResponse = {
  id: string;
  name: string;
  owner_id: string;
  created_at: string;
};

export type MembershipResponse = {
  id: string;
  user_id: string;
  group_id: string;
  role: string;
  joined_at: string;
};

export type UserLogin = {
  email: string;
  password: string;
};

export type UserCreate = {
  email: string;
  username: string;
  password: string;
};

export type GroupCreate = {
  name: string;
};

export type GroupJoinRequest = {
  invite_code: string;
};

export type LocationPinResponse = {
  id: string;
  osm_building_id: number;
  lat: number;
  lng: number;
  label: string | null;
  created_at: string;
};

export type LocationPinCreate = {
  osm_building_id: number;
  lat: number;
  lng: number;
  building_geometry: Polygon | MultiPolygon;
  label?: string | null;
};

/** How a building's {@link SelectedBuilding.selectionKey} was derived. */
export type BuildingIdentityStrategy = "osm" | "feature" | "geometry";

export type SelectedBuilding = {
  /**
   * Real OSM building id when the tile exposes one (osm_id property or a
   * numeric feature id), otherwise null. Null buildings can still be
   * highlighted, but cannot be persisted as a pin.
   */
  osmBuildingId: number | null;
  geometry: Polygon | MultiPolygon;
  centroid: {
    lat: number;
    lng: number;
  };
  /**
   * Guaranteed-unique per-footprint key for hover/selection UI. Always
   * incorporates a geometry hash so buildings that share (or lack) an osm_id
   * never collapse into a single highlight.
   */
  selectionKey: string;
  /** Which identifier the selectionKey was derived from (diagnostics/persistence). */
  identityStrategy: BuildingIdentityStrategy;
};

/** Status of an async single-image 3D generation submission. */
export type SubmissionStatus = "processing" | "ready" | "failed";

export type SubmissionResponse = {
  id: string;
  pin_id: string;
  status: SubmissionStatus;
  mesh_url: string | null;
  error_message: string | null;
  created_at: string;
};

export type MapObjectResponse = {
  id: string;
  pin_id: string;
  osm_building_id: number;
  lat: number;
  lng: number;
  mesh_url: string;
  /** Yaw in degrees clockwise from north applied when rendering the mesh. */
  heading: number;
  /** Uniform size multiplier applied on top of the client-side auto-fit. */
  scale: number;
};

export type MapStateResponse = {
  group_id: string;
  pins: LocationPinResponse[];
  objects: MapObjectResponse[];
};

/** Kinds of actions recorded on a group's activity timeline. */
export type ActivityEventType = "pin_created" | "object_placed";

/**
 * Denormalized snapshot stored with each event so the feed renders without
 * refetching the target. Fields are best-effort and may be absent on old rows.
 */
export type ActivityEventPayload = {
  label?: string | null;
  lat?: number;
  lng?: number;
  osm_building_id?: number;
  pin_id?: string;
  map_object_id?: string;
};

export type ActivityEventResponse = {
  id: string;
  event_type: ActivityEventType;
  actor_user_id: string;
  actor_username: string;
  target_type: string;
  target_id: string | null;
  payload: ActivityEventPayload | null;
  created_at: string;
};

export type ActivityListResponse = {
  events: ActivityEventResponse[];
};

/** One day on the map-growth chart. */
export type GrowthPoint = {
  date: string;
  count: number;
  cumulative: number;
};

export type GrowthResponse = {
  points: GrowthPoint[];
  total: number;
};

/** A contributed place surfaced in the in-map discovery view. */
export type PlaceSummary = {
  pin_id: string;
  map_object_id: string;
  label: string | null;
  lat: number;
  lng: number;
  contributor_username: string | null;
  created_at: string;
};

export type PlacesResponse = {
  places: PlaceSummary[];
};
