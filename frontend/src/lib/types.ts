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

export type SelectedBuilding = {
  osmBuildingId: number;
  geometry: Polygon | MultiPolygon;
  centroid: {
    lat: number;
    lng: number;
  };
};

export type CaptureMethod = "images" | "video";

export type ContributionSubmissionDraft = {
  pinId: string;
  groupId: string;
  userId: string;
  osmBuildingId: number;
  lat: number;
  lng: number;
  captureMethod: CaptureMethod;
  files: File[];
};

export type MapObjectResponse = {
  id: string;
  pin_id: string;
  lat: number;
  lng: number;
};

export type MapStateResponse = {
  group_id: string;
  pins: LocationPinResponse[];
  objects: MapObjectResponse[];
};
