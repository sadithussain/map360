# Collaborative 3D World Mapping Platform — Build Checklist

A working task list derived from `outline.MD`. Items are grouped by product area and roughly ordered from foundational to advanced. Check items off as they are completed.

---

## 1. Foundation and Project Setup

- [x] Decide on tech stack for backend (FastAPI confirmed), PWA frontend (Vite + React + TS), and 3D rendering library (Three.js / React Three Fiber)
- [x] Set up monorepo structure with `backend/` and `frontend/` folders
- [x] Add dependency management files (`requirements.txt` / `pyproject.toml`, `package.json`)
- [x] Configure environment variable handling (`.env`, settings module)
- [x] Set up Supabase Postgres (replaces local PostgreSQL) for development
- [x] Configure object storage for media uploads (Supabase Storage settings/env in place)
- [x] Configure PWA basics (web app manifest, service worker, installable app shell)
- [x] Add Alembic (or equivalent) for database migrations
- [x] Set up linting, formatting, and pre-commit hooks
- [x] Create initial README with setup and run instructions

---

## 2. User Accounts and Authentication

- [x] Finish `User` SQLAlchemy model wiring (relationships compile end-to-end)
- [x] Implement async database engine and `AsyncSession` factory in `db/database.py`
- [x] Implement user registration endpoint (`POST /users/register`)
- [x] Implement login endpoint with password verification
- [x] Add JWT (or session) token issuance and validation
- [x] Add auth dependency for protecting routes
- [x] Implement "get current user" endpoint (`GET /users/me`)
- [x] Handle duplicate username/email errors at the API layer
- [x] Add basic password reset / change password flow (optional v1)

---

## 3. Groups, Memberships, and Privacy Isolation

- [x] Define `Group` model (id, name, owner, created_at)
- [x] Define `Membership` model (user, group, role, joined_at)
- [x] Create Pydantic schemas for groups and memberships
- [x] Endpoint to create a new group
- [x] Endpoint to join a group (invite code or invitation)
- [x] Endpoint to list a user's groups
- [x] Endpoint to list members of a group
- [x] Endpoint to leave / remove a member from a group
- [x] Enforce group-only visibility on every group-scoped resource
- [x] Add permission helpers ("is member of group", "is owner of group")

---

## 4. Map Experience (Group-Scoped World State)

- [X] Build the initial frontend shell (auth screens, group selector)
- [x] Render a minimal grey geographic base map (streets + building outlines, no user-generated models)
- [x] Implement camera controls: zoom, pan, navigate
- [x] Load and render group-specific map state from the backend
- [x] Switch active group and reload the corresponding map layer
- [x] Cache map state for smoother navigation
- [x] Handle empty group state ("no contributions yet") gracefully

---

## 5. Location Contribution Flow

- [x] Add "Add location" button to enter building-selection mode (workspace only)
- [x] Make base-map building footprints interactive (MapLibre click + queryRenderedFeatures)
- [x] Extract osm_id, geometry, and centroid from the clicked building feature
- [x] Hover + selected-building visual feedback on the map
- [x] Confirmation UI after building selection (continue / pick another / cancel)
- [x] `LocationPin` model (group, user, osm_building_id, lat, lng, building_geometry, label, created_at)
- [x] Endpoint to create a location pin from a selected building within a group
- [x] ~~UI flow to choose capture method (3 images vs ~5 second video)~~ Superseded by single-photo capture (TRELLIS single-image-to-3D pivot)
- [x] ~~Capture UI for three angled images (left / center / right)~~ Superseded by single-photo capture
- [x] ~~Capture UI for short horizontal video sweep~~ Superseded by single-photo capture
- [x] Single-photo capture UI (one high-quality image; camera or file input)
- [x] Guidance tooltip: capture the "clearest, most central angle" of the storefront
- [x] Client-side validation (single image, size, format)
- [x] Attach building metadata (osm_building_id, centroid), group ID, and user ID to each submission

---

## 6. Media Upload and Submission Tracking

- [x] Define `MediaSubmission` model (pin, user, group, source image key, status, mesh keys/url, error)
- [x] Endpoint to accept a single-image multipart upload and start generation
- [x] Endpoint to poll a submission's processing status
- [x] Endpoint to list submissions for a pin / group
- [x] Track submission processing status (processing, ready, failed)
- [x] Store original image in Supabase Storage with safe key naming

---

## 7. 3D Processing Pipeline

- [x] Decide on processing approach — **TRELLIS single-image-to-3D on Colab Gradio; FastAPI middleman via `gradio_client`** (research + infra setup complete)
- [x] TRELLIS Gradio client helper (`gradio_client` → active `*.gradio.live` URL)
- [x] FastAPI `BackgroundTasks` job (image → Colab → `.glb` → Supabase Storage → DB) instead of Celery/RQ for v1
- [x] Background job: pass source image to TRELLIS, store resulting `.glb`
- [x] Align generated model to pin's real-world coordinates
- [x] Update submission status on success / failure (`processing` → `ready` / `failed`)
- [x] ~~Retry handling for failed jobs (heavier queue such as Celery/Redis only if needed later)~~ Deferred — `BackgroundTasks` is the v1 approach; durable retry (Celery/Redis) only if needed later

---

## 8. Generated Models and Map Objects

- [x] Define `MapObject` model (group, pin, submission, coordinates, `mesh_url`)
- [x] Include map objects (with `mesh_url`) in the group map-state response
- [x] Endpoint to list map objects for a group (with bounding-box filter)
- [x] Endpoint to fetch a single map object with its mesh URL
- [x] Frontend loader for generated 3D meshes (Three.js MapLibre custom layer; `.glb` anchored at the pin's real-world lat/lng, normalized to ~12 m and grounded)
- [x] Hide the default grey building (2D fill + 3D extrusion) under each contributed mesh so the generated model replaces the stock footprint
- [x] Real-time or near-real-time update of group map when new object is added (silent map-state polling, ~20s)
- [x] Visual indicator for newly added objects (short emissive pulse on the mesh)
- [x] Manual mesh orientation: any group member can select a placed mesh and rotate it (persisted `heading` on `MapObject`, live slider preview, applied in the mesh layer)

---

## 9. Social / Collaborative Features

- [x] Group activity feed model (event type, actor, target, timestamp)
- [x] Endpoint to fetch recent activity for a group
- [x] UI panel for group activity feed
- [x] Contributions log view (who added what, where, when)
- [x] Map growth indicator (count over time, simple chart)
- [x] In-map discovery view to navigate contributed places

---

## 10. Quality (Backend Tests)

- [x] Unit tests for CRUD layer (users, groups, location pins, activity)
- [x] Unit tests for service layer (auth, groups, map/pin creation, activity)
- [x] Router coverage for auth, groups, pins, submissions, activity
- [x] Refine shared test fixtures/helpers to reduce duplication

---

## 11. Optional Future Expansion

- [ ] Time-based evolution of maps (historical layers)
- [ ] Ratings or tagging of locations
- [ ] Reputation system for contributors
- [ ] Shared public maps outside private groups
- [ ] Indoor mapping (stores, malls, campuses)
