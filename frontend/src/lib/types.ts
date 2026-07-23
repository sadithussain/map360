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
};

export type MapStateResponse = {
  group_id: string;
  pins: LocationPinResponse[];
  objects: MapObjectResponse[];
};
