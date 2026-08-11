# Map360 — Tech Stack Reference

A living reference of the technologies used in this project: **where** they live in the repo, **how** they are applied, and **why** they were chosen. Pair this with [`outline.MD`](outline.MD) (product vision) and [`checklist.MD`](checklist.MD) (build roadmap).

---

## High-Level Architecture

```
Browser (Vite + React PWA)
    │  HTTP + JWT Bearer
    ▼
FastAPI (uvicorn)
    │  async SQLAlchemy + asyncpg
    ▼
Supabase Postgres          Supabase Storage (source images + generated .glb meshes)
                                    ▲
                                    │  upload .glb
FastAPI BackgroundTask ──gradio_client──▶ Colab GPU (TRELLIS via Gradio)
```

The repo is a monorepo with two apps:

| Path | Role |
| ---- | ---- |
| `backend/` | FastAPI API, SQLAlchemy models, Alembic migrations, pytest suite |
| `frontend/` | Vite + React + TypeScript PWA (map UI, auth screens, contribution flow) |
| `project details/` | Product docs (outline, checklist, this file) |

> **Important boundary:** Supabase provides hosted **Postgres** and **object storage** only. Authentication is owned by the application (bcrypt + JWT), not Supabase Auth.

---

## Backend

### FastAPI

| | |
| --- | --- |
| **Where** | `backend/app/main.py`, `backend/app/routers/`, `backend/app/dependencies/` |
| **How** | ASGI web framework. Routers expose users, groups, map state, media submissions, map-object, and group social endpoints (activity feed, map growth, discoverable places under `app/routers/activity_router.py`). Dependencies inject the current user and DB session. CORS is configured for the Vite dev origin. Custom validation error handler flattens Pydantic errors into a single `detail` string for the UI. Generation runs as FastAPI `BackgroundTasks` after upload. |
| **Why** | Async-first Python API with automatic OpenAPI docs (`/docs`), strong typing via Pydantic, and a clear dependency-injection model that fits JWT-protected routes. |

### Uvicorn

| | |
| --- | --- |
| **Where** | Run via `uvicorn app.main:app --reload` (see root `README.md`) |
| **How** | ASGI server that hosts the FastAPI app locally (and can host it in production). |
| **Why** | Standard, fast ASGI server for FastAPI; supports reload during development. |

### SQLAlchemy 2.0 (async)

| | |
| --- | --- |
| **Where** | `backend/app/db/database.py`, `backend/app/models/`, `backend/app/crud/` |
| **How** | Async engine + `AsyncSession` factory. Models (`User`, `Group`, `Membership`, `LocationPin`, invite codes) inherit from a shared `Base`. CRUD modules and services use request-scoped sessions from `get_db`. Engine is tuned for Supabase’s transaction pooler (port `6543`) with `NullPool` and disabled prepared-statement caching when needed. |
| **Why** | Mature ORM with first-class async support, clear model relationships for groups/memberships/pins, and one metadata surface for Alembic autogenerate. |

### asyncpg

| | |
| --- | --- |
| **Where** | Declared in `backend/requirements.txt`; used via `postgresql+asyncpg://` in `DATABASE_URL` |
| **How** | Native async PostgreSQL driver under SQLAlchemy. Connection URL must use an async scheme (validated in `app/core/config.py`). |
| **Why** | High-performance async DB access that matches FastAPI’s async request handlers. |

### Alembic

| | |
| --- | --- |
| **Where** | `backend/alembic/`, `backend/alembic.ini`, `backend/alembic/env.py` |
| **How** | Schema migrations versioned under `alembic/versions/`. `env.py` loads `DATABASE_URL` from app settings and imports models so autogenerate sees current metadata. Apply with `alembic upgrade head`. |
| **Why** | Reproducible schema evolution across environments without manual SQL or destructive resets. |

### Pydantic / pydantic-settings

| | |
| --- | --- |
| **Where** | `backend/app/schemas/`, `backend/app/core/config.py` |
| **How** | Request/response schemas validate API payloads. `Settings` loads typed config from environment / `.env` (`DATABASE_URL`, JWT secrets, Supabase storage keys). |
| **Why** | Runtime validation, clear API contracts, and type-safe configuration without ad-hoc env parsing. |

### python-dotenv

| | |
| --- | --- |
| **Where** | Loaded indirectly via pydantic-settings (`env_file=".env"`) |
| **How** | Local `.env` values (from `.env.example`) populate settings without committing secrets. |
| **Why** | Standard local-dev pattern for secrets and connection strings. |

### bcrypt

| | |
| --- | --- |
| **Where** | `backend/app/core/security.py` |
| **How** | Hashes passwords on register; verifies on login. Inputs are capped at bcrypt’s 72-byte limit. Hashes are stored on `User`; plain text is never persisted. |
| **Why** | Industry-standard password hashing with a slow, salted algorithm suitable for credential storage. |

### PyJWT

| | |
| --- | --- |
| **Where** | `backend/app/core/security.py`, `backend/app/dependencies/auth.py` |
| **How** | Issues HS256 access tokens (`sub`, `iat`, `exp`) on login. Auth dependency decodes the Bearer token and loads the current user for protected routes. |
| **Why** | Stateless, application-owned auth that does not depend on Supabase Auth and keeps group/map authorization under our control. |

### python-multipart

| | |
| --- | --- |
| **Where** | `backend/requirements.txt`; used by map/media upload routes in `backend/app/routers/map_router.py` |
| **How** | Enables FastAPI form/file parsing for the single-image contribution upload (`multipart/form-data`). |
| **Why** | Required dependency for the media submission endpoint that accepts the source photo before TRELLIS generation. |

### httpx + pytest + pytest-asyncio

| | |
| --- | --- |
| **Where** | `backend/tests/`, `backend/pyproject.toml` (`[tool.pytest.ini_options]`) |
| **How** | Async-aware test runner. `httpx` exercises API routes; `conftest.py` sets safe placeholder env vars so settings import without a live DB for unit/router tests. |
| **Why** | Reliable automated coverage for auth, groups, permissions, and map-state behavior as the API grows. |

### Ruff

| | |
| --- | --- |
| **Where** | Config in `backend/pyproject.toml`; hooked in `.pre-commit-config.yaml` |
| **How** | Lints and formats Python under `backend/` (including `--fix` on commit). FastAPI `Depends`/`Query` callables are allowlisted for bugbear rules. |
| **Why** | Fast, single-tool lint + format for Python 3.12 with consistent style across the backend. |

---

## Data & Infrastructure

### Supabase Postgres

| | |
| --- | --- |
| **Where** | Connection via `DATABASE_URL` in `backend/.env`; models in `backend/app/models/` |
| **How** | Hosted PostgreSQL stores users, groups, memberships, invite codes, and location pins (including GeoJSON-like building geometry in JSONB). Accessed only through the FastAPI app’s async SQLAlchemy layer. |
| **Why** | Managed Postgres with a connection string that works locally and in cloud deploys, without running a database container for early development. |

### Supabase Storage

| | |
| --- | --- |
| **Where** | Settings in `backend/app/core/config.py` / `.env.example` (`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_MEDIA_BUCKET`, `SUPABASE_MESH_BUCKET`); helper in `backend/app/services/storage.py` |
| **How** | Holds the uploaded source photo (`media` bucket) and the generated `.glb` mesh (`meshes` bucket). The FastAPI backend uploads with the service-role key via the `supabase` Python client and returns public URLs to the frontend. |
| **Why** | Object storage colocated with the same Supabase project as Postgres, suitable for scan media and generated meshes without standing up a separate asset store. |

### Google Colab + Gradio + gradio_client (TRELLIS)

| | |
| --- | --- |
| **Where** | Model runs in a Colab T4 notebook exposing a Gradio server at a temporary `https://<hash>.gradio.live` URL; backend client in `backend/app/services/trellis.py` (config: `TRELLIS_GRADIO_URL`, `TRELLIS_GRADIO_API_NAME`) |
| **How** | Microsoft's TRELLIS performs single-image-to-3D: one storefront/landmark photo is hallucinated into a complete `.glb` mesh. FastAPI acts as the middleman — `gradio_client.Client(TRELLIS_GRADIO_URL)` forwards the uploaded image to Colab and receives the generated `.glb` back. |
| **Why** | The model is far too heavy to host on the app backend; Colab provides a free GPU, and `gradio_client` gives a stable Python call surface over the notebook's live endpoint without hosting the model ourselves. |

### OpenFreeMap / OpenMapTiles (map tiles)

| | |
| --- | --- |
| **Where** | `frontend/src/components/WorldMap.tsx` (style URL), building layers via OpenMapTiles `building` source layer in `buildingSelection.ts` |
| **How** | Base map style loaded from `https://tiles.openfreemap.org/styles/liberty`, then restyled to a grey “blank world” look. Building footprints from the vector tile source drive selection, hover, and pin placement (OSM building ids / geometry). |
| **Why** | Free vector basemap with real-world streets and building outlines—enough for navigation and contribution without hosting custom tiles yet. |

---

## Frontend

### Vite

| | |
| --- | --- |
| **Where** | `frontend/vite.config.ts`, scripts in `frontend/package.json` |
| **How** | Dev server (`npm run dev` on port 5173), production bundler (`npm run build`), and plugin host for React, Tailwind, and PWA. |
| **Why** | Fast HMR and modern ESM tooling for a TypeScript React app. |

### React 18 + TypeScript

| | |
| --- | --- |
| **Where** | `frontend/src/` (`pages/`, `components/`, `hooks/`, `lib/`, `context/`) |
| **How** | UI for landing map, auth, groups, workspace shell, building selection, single-photo capture, and generated-mesh display on the map. Shared types live in `lib/types.ts`; API client in `lib/api.ts`. |
| **Why** | Component model fits interactive map + multi-step contribution flows; TypeScript keeps API contracts aligned with backend schemas. |

### React Router

| | |
| --- | --- |
| **Where** | `frontend/src/main.tsx`, `App.tsx`, `ProtectedRoute.tsx`, page navigation |
| **How** | Client-side routes for `/`, `/about`, `/login`, `/register`, `/groups`, `/app`. Protected/public-only wrappers gate access by auth (and active group for the workspace). |
| **Why** | Standard SPA routing with clear auth boundaries between marketing/map, account, and group workspace. |

### Tailwind CSS v4 (`@tailwindcss/vite`)

| | |
| --- | --- |
| **Where** | `frontend/src/index.css` (`@import "tailwindcss"`), utility classes across components |
| **How** | Utility-first styling via the Vite plugin—no separate PostCSS config required for the current setup. |
| **Why** | Rapid, consistent layout and spacing for auth, groups, and map overlay panels without a heavy CSS architecture. |

### MapLibre GL JS

| | |
| --- | --- |
| **Where** | `frontend/src/components/WorldMap.tsx`, `lib/maplibreSetup.ts`, `lib/mapGreyStyle.ts`, `lib/buildingSelection.ts`, `lib/mapGeolocation.ts`, `lib/meshLayer.ts` |
| **How** | Renders the interactive 2D/3D-tilted geographic map: pan/zoom, grey restyle, geolocation-based initial view, GeoJSON pin layers, and `queryRenderedFeatures` for building pick/hover/select. Hosts a Three.js `CustomLayerInterface` for placed `.glb` meshes. Worker setup avoids CSP/worker path issues in Vite. |
| **Why** | Open-source Mapbox GL compatible renderer—full control of basemap styling, feature querying, and custom WebGL layers without a Mapbox license for the core map experience. |

### Turf.js (`@turf/boolean-point-in-polygon`, `@turf/flatten`, `@turf/helpers`)

| | |
| --- | --- |
| **Where** | `frontend/src/lib/buildingSelection.ts` |
| **How** | Geometric helpers for building hit-testing and selection (point-in-polygon checks, flattening multipolygons, constructing Turf points from click coordinates). |
| **Why** | Reliable geospatial predicates on the client when resolving which building footprint the user selected. |

### Three.js (MapLibre custom layer)

| | |
| --- | --- |
| **Where** | `frontend/src/lib/meshLayer.ts` (`GeneratedMeshLayer`), wired from `WorldMap.tsx`; uses `three` + `GLTFLoader` / `RoomEnvironment` |
| **How** | MapLibre `CustomLayerInterface` loads each map object’s `.glb`, anchors it at the pin’s lat/lng via the mercator transform, normalizes/grounds the mesh to cover the stock building extrusion, and can pulse newly appeared objects. Group map state is refreshed by silent polling (~20s) in `useGroupMapState`. |
| **Why** | Places reconstructed models in real-world map space without a separate 3D canvas. Bare Three.js fits MapLibre’s custom-layer API better than React Three Fiber for this use case. |

> **Note:** `@react-three/fiber` and `@react-three/drei` remain in `frontend/package.json` but are unused; mesh display goes through the MapLibre custom layer above.

### vite-plugin-pwa (Workbox)

| | |
| --- | --- |
| **Where** | `frontend/vite.config.ts`, registration in `frontend/src/main.tsx`, icons under `frontend/public/` |
| **How** | Generates web app manifest + service worker. `registerSW({ immediate: true })` enables installability and caching of static assets. Dev PWA mode is enabled for local testing. |
| **Why** | Mobile-friendly installable app shell for field capture (camera/media) without shipping a native client in v1. |

### ESLint + typescript-eslint

| | |
| --- | --- |
| **Where** | `frontend/eslint.config.js`, `npm run lint` / pre-commit hook |
| **How** | Lints TS/TSX with React Hooks and React Refresh rules. |
| **Why** | Catches common React/TS mistakes before they land in review. |

---

## Cross-Cutting Tooling

### Pre-commit

| | |
| --- | --- |
| **Where** | `.pre-commit-config.yaml` at repo root |
| **How** | On commit: trailing whitespace / EOF / YAML / large-file / private-key checks; Ruff lint+format for `backend/`; ESLint for `frontend/` TS/TSX. |
| **Why** | Shared quality gate so Python and frontend style stay consistent without relying on each developer’s editor alone. |

### Environment configuration

| | |
| --- | --- |
| **Where** | `backend/.env.example`, `frontend/.env.example` |
| **How** | Backend: DB, JWT, Supabase storage. Frontend: `VITE_API_BASE_URL` pointing at the API (default `http://127.0.0.1:8000`). |
| **Why** | Separates secrets and deploy-specific URLs from source control while documenting required keys. |

### Node.js / npm & Python 3.12+

| | |
| --- | --- |
| **Where** | Frontend via `package.json`; backend via `requirements.txt` / Ruff `target-version = "py312"` |
| **How** | Two runtimes for the two halves of the monorepo (see root README prerequisites). |
| **Why** | Matches the checklist decision: Python async API + modern TypeScript SPA. |

---

## Planned / Not Yet Introduced

These appear on the roadmap (`checklist.MD`) but are **not** in the dependency tree yet:

| Area | Likely direction | Purpose |
| ---- | ---------------- | ------- |
| Heavier background jobs | Celery/Redis (only if `BackgroundTasks` proves insufficient) | Durable retries / dead-lettering for generation jobs that outlive a process restart |
| Instant map updates | WebSocket (v1: silent map-state poll ~20s + submission-status poll) | Push new map objects to group members without polling latency |
| Observability | Structured logging, Sentry | Errors and ops visibility |
| Containers / CI | Docker, GitHub Actions (or similar) | Reproducible deploys and automated lint/test/build |

When those land, update this file with the same **where / how / why** pattern.

> **Ops note (TRELLIS):** the Colab Gradio URL is ephemeral — refresh `TRELLIS_GRADIO_URL` whenever the notebook restarts. Create the `media` and `meshes` Supabase Storage buckets (public read, or signed reads) before the first upload. `BackgroundTasks` do not survive an API process restart, which is acceptable for the Colab prototype; stranded `processing` rows can be retried later.

---

## Quick “Who Owns What” Cheatsheet

| Concern | Technology |
| ------- | ---------- |
| HTTP API | FastAPI + Uvicorn |
| Persistence | SQLAlchemy + asyncpg → Supabase Postgres |
| Schema changes | Alembic |
| Auth | bcrypt + PyJWT (app-owned) |
| Media files + generated meshes | Supabase Storage (`media` + `meshes` buckets) |
| Single-image 3D generation | TRELLIS on Colab Gradio via `gradio_client` (FastAPI `BackgroundTasks`) |
| Basemap & building pick | MapLibre + OpenFreeMap tiles + Turf |
| Generated 3D model display | Three.js via MapLibre custom layer (`meshLayer.ts`) |
| Near-real-time map refresh | Silent HTTP poll of group map state (~20s) |
| Installable client | Vite PWA (vite-plugin-pwa) |
| UI styling | Tailwind CSS v4 |
| Routing | React Router |
| Lint / format | Ruff (Python), ESLint (TS), pre-commit |
| Tests | pytest + httpx (backend) |
