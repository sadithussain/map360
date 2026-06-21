/** API response shapes mirrored from the backend Pydantic schemas. */

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
