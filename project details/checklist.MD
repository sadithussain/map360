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
- [ ] Endpoint to create a new group
- [ ] Endpoint to join a group (invite code or invitation)
- [ ] Endpoint to list a user's groups
- [ ] Endpoint to list members of a group
- [ ] Endpoint to leave / remove a member from a group
- [ ] Enforce group-only visibility on every group-scoped resource
- [ ] Add permission helpers ("is member of group", "is owner of group")

---

## 4. Map Experience (Group-Scoped World State)

- [ ] Build the initial frontend shell (auth screens, group selector)
- [ ] Render a minimal grey 3D world map (no default buildings)
- [ ] Implement camera controls: zoom, pan, navigate
- [ ] Load and render group-specific map state from the backend
- [ ] Switch active group and reload the corresponding map layer
- [ ] Cache map state for smoother navigation
- [ ] Handle empty group state ("no contributions yet") gracefully

---

## 5. Location Contribution Flow

- [ ] UI to drop a pin on a real-world location on the map
- [ ] `LocationPin` model (group, user, lat, lng, label, created_at)
- [ ] Endpoint to create a location pin within a group
- [ ] UI flow to choose capture method (3 images vs ~5 second video)
- [ ] Capture UI for three angled images (left / center / right)
- [ ] Capture UI for short horizontal video sweep
- [ ] Client-side validation (file size, count, duration, format)
- [ ] Attach GPS, group ID, and user ID to each submission

---

## 6. Media Upload and Submission Tracking

- [ ] Define `MediaSubmission` model (pin, user, group, media type, storage keys, status)
- [ ] Endpoint to request a signed upload URL (or accept multipart upload)
- [ ] Endpoint to finalize a submission after upload completes
- [ ] Endpoint to list submissions for a pin / group
- [ ] Track submission processing status (pending, processing, ready, failed)
- [ ] Store original media in object storage with safe key naming
- [ ] Enforce per-user / per-group upload quotas (optional v1)

---

## 7. 3D Processing Pipeline (Conceptual Placeholders)

- [ ] Decide on processing approach (photogrammetry service, NeRF, third-party API, etc.)
- [ ] Define `GeneratedModel` model (submission, storage key, format, status)
- [ ] Background worker / queue (Celery, RQ, or equivalent) for processing jobs
- [ ] Worker job: pull media, run reconstruction, store resulting mesh
- [ ] Align generated model to pin's real-world coordinates
- [ ] Update submission and pin status on success / failure
- [ ] Retry and dead-letter handling for failed jobs

---

## 8. Generated Models and Map Objects

- [ ] Define `MapObject` model (group, pin, generated_model, transform/coordinates)
- [ ] Endpoint to list map objects for a group (with pagination / bounding box)
- [ ] Endpoint to fetch a single map object with its mesh URL
- [ ] Frontend loader for generated 3D meshes
- [ ] Real-time or near-real-time update of group map when new object is added (WebSocket / polling)
- [ ] Visual indicator for newly added objects

---

## 9. Social / Collaborative Features

- [ ] Group activity feed model (event type, actor, target, timestamp)
- [ ] Endpoint to fetch recent activity for a group
- [ ] UI panel for group activity feed
- [ ] Contributions log view (who added what, where, when)
- [ ] Map growth indicator (count over time, simple chart)
- [ ] In-map discovery view to navigate contributed places

---

## 10. Content Boundaries and Moderation

- [ ] Enforce hard privacy isolation between groups in all queries
- [ ] Validation that submissions belong to a real, accessible pin in the user's group
- [ ] Duplicate detection (same pin scanned excessively in short window)
- [ ] Basic content checks (file types, dimensions, duration limits)
- [ ] Group owner tools to remove a submission or map object
- [ ] Report / flag submission endpoint (optional v1)

---

## 11. Quality, Observability, and Deployment

- [ ] Unit tests for CRUD and service layer
- [ ] Integration tests for auth, groups, submissions
- [ ] Frontend component / interaction tests
- [ ] Structured logging across backend and worker
- [ ] Error tracking (Sentry or similar)
- [ ] Health check and readiness endpoints
- [ ] Containerize backend, worker, and frontend (Dockerfiles)
- [ ] CI pipeline (lint, test, build)
- [ ] Deployment configuration for staging and production

---

## 12. Optional Future Expansion

- [ ] Time-based evolution of maps (historical layers)
- [ ] Ratings or tagging of locations
- [ ] Reputation system for contributors
- [ ] Shared public maps outside private groups
- [ ] Indoor mapping (stores, malls, campuses)
