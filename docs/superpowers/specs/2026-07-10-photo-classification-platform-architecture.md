# Photo Classification Platform — Architecture Plan

Date: 2026-07-10

## Context

Assessment task: a cloud-deployable web platform where users register/login,
upload a photo + metadata, and receive a classification result; and an admin
can filter/search submissions. Hard requirement: **≥2 microservices,
containerized with Docker**, plus DB justification, security, K8s strategy, and
CI/CD.

Starting point (already built): a **modular-monolith FastAPI app** with
`fastapi-users` (JWT + cookie auth), `sqladmin` admin panel, SQLite, Jinja
login/register/home screens, and a clean self-contained `app/auth/` package
(see `docs/superpowers/specs/2026-07-09-auth-module-design.md`). This existing
work is reused, not thrown away — `app/auth/` becomes the Auth service almost
verbatim, and the `sqladmin` setup moves into the Submissions service.

**Approved decisions:** 3 services · pluggable classifier with mock default ·
synchronous REST between Submissions and Classification · docker-compose fully
runs locally, K8s + CI/CD written and explained but not deployed to a live
cluster.

## Target architecture

One Git **monorepo**, three independently-deployable FastAPI services + a shared
library. `docker-compose up` brings the whole platform up locally.

```
repo/
  services/
    auth/            # register/login, JWT issuing, user store  (from app/auth/)
    submissions/     # photo upload + metadata + admin panel, calls classifier
    classification/  # image classification + safety gate (pluggable, mock default)
  libs/shared/       # JWT verification, settings base, common Pydantic schemas
  deploy/k8s/        # Deployments, Services, Ingress, HPA, Secrets, ConfigMaps (written, not deployed)
  .github/workflows/ # lint + test + build + push + (documented) deploy
  docker-compose.yml
  .env.example
  docs/              # README, architecture.drawio / .png, this plan
```

### Services and responsibilities

1. **Auth service** (port 8001) — owns the `users` table. Endpoints:
   `POST /auth/register`, `POST /auth/jwt/login`, `POST /auth/jwt/logout`,
   `GET /users/me`. Issues JWTs signed with a shared secret. Reuses the existing
   `fastapi-users` wiring from `app/auth/`. Keeps its own sqladmin over users
   (optional) or exposes users read-only.

2. **Submissions service** (port 8002) — owns the `submissions` table. Endpoints:
   - `POST /submissions` — multipart upload: photo file + metadata (name, age,
     place_of_living, gender, country_of_origin, optional description). Validates,
     stores photo in object storage, calls Classification synchronously, persists
     metadata + object key + classification result + timestamps.
   - `GET /submissions/me` — the caller's own submissions.
   - `GET /submissions/{id}` — single record (owner or admin).
   - `GET /admin/submissions` — **admin-only**, filter/search by `age` (range),
     `gender`, `place_of_living`, `country_of_origin`; paginated, sorted by
     `created_at`.
   - Hosts the **admin panel** via `sqladmin` (column filters cover the required
     admin filters), gated by the existing `AdminAuth` superuser backend.

3. **Classification service** (port 8003) — stateless. `POST /classify` takes an
   image, returns `{category, confidence, safe: bool, reasons: [...]}`. A
   `Classifier` Protocol with a `MockClassifier` default (deterministic result +
   a basic safety verdict); README documents swapping in a real model. This
   service doubles as the **content-safety gate**.

### Communication

- **Client → services**: REST/JSON (+ the server-rendered login/register/home
  and admin HTML). In compose, a lightweight reverse proxy (or direct ports) —
  in K8s, an Ingress routes `/auth`→auth, `/api`(+`/admin`)→submissions.
- **Submissions → Classification**: synchronous HTTP (`httpx`) on upload.
- **Auth propagation**: JWT is validated **locally in each service** using the
  shared secret (`libs/shared`), so no chatty per-request calls back to Auth.
  This is the key microservice auth pattern to highlight in the diagram.

## Data layer

**Database: PostgreSQL** (replaces SQLite, which stays fine for local unit tests).
Justification to write up: relational integrity + ACID for submissions;
first-class **indexing** for the admin filters; mature ecosystem; managed
offerings (RDS/Cloud SQL) in prod. **Database-per-service** ownership: Auth owns
`users`, Submissions owns `submissions` (separate logical DBs / schemas on one
Postgres instance for the assessment; note the split-to-separate-instances path).

**Object storage: MinIO** (S3-compatible) in compose/K8s-dev; maps 1:1 to
S3/GCS in prod. Photos live here; the DB stores only the **object key**, never
the bytes.

**Schema (`submissions`):** `id (uuid pk)`, `user_id (uuid, fk→users)`, `name`,
`age (int)`, `place_of_living`, `gender (enum)`, `country_of_origin`,
`description (nullable)`, `photo_key`, `classification (jsonb: category,
confidence, safe)`, `created_at`, `updated_at`.

**Indexing:** btree indexes on `age`, `gender`, `country_of_origin`,
`place_of_living` (the admin filter columns) and on `user_id` + `created_at`
(ownership queries / sorting). Justify each in the README.

**Migrations: Alembic** in Auth and Submissions (replaces the current
`create_db_and_tables()` lifespan call). One migration env per owning service.

## Security & safety rules (call these out explicitly in the README)

- **Auth**: JWT bearer + secure http-only cookie (already in place); password
  hashing via `fastapi-users` (argon2/bcrypt); admin-only RBAC on `/admin/*`.
- **Upload safety gate** (Submissions): enforce max file size; validate real
  content type by **magic bytes** (not just the client header); allow-list
  image MIME types; cap image dimensions; store under a server-generated UUID
  key (never the client filename); **strip EXIF** (privacy/geolocation).
- **Content safety** (Classification): the classifier returns a `safe` verdict;
  Submissions **rejects unsafe uploads** (e.g. 422) and records the reason.
- **Input validation**: Pydantic models — `age` bounded range, `gender` enum,
  string length caps, optional description.
- **Rate limiting** on the upload endpoint.
- **Secrets** never in code — env vars locally, K8s Secrets in cluster.
- Each rule documented as *what / where / why* per the task.

## Cloud / Kubernetes strategy (manifests written, not deployed)

- One **Deployment + Service** per microservice; **Ingress** for path routing.
- **HPA** on the Classification service (CPU-bound, independently scalable —
  the concrete payoff of the 3-service split).
- **Secrets** for JWT secret + DB creds + MinIO creds; **ConfigMaps** for
  non-secret config; note external secret managers (Sealed Secrets / cloud SM).
- **Postgres & object storage**: managed services in prod (RDS/Cloud SQL, S3/GCS);
  StatefulSet Postgres + MinIO for a self-contained dev cluster.
- **Observability**: structured JSON logging; `/health` + `/ready` probes;
  Prometheus `/metrics` via `prometheus-fastapi-instrumentator`; note on
  OpenTelemetry tracing across the sync call chain.

## CI/CD (GitHub Actions — YAML written; deploy step documented)

- **Lint** (`ruff`), **test** (`pytest`), per-service **Docker build**, **push**
  to **GHCR** (matrix over the 3 services).
- **Deploy** job present but gated/commented — `kubectl apply`/Helm against a
  cluster, explained in the README rather than run live.

## Deliverables checklist

- Monorepo with source + README (setup, usage, per-service API docs / Swagger).
- `docker-compose.yml` + `.env.example` (extend the existing `.env.example`).
- K8s manifests under `deploy/k8s/`; GitHub Actions under `.github/workflows/`.
- **draw.io block diagram** (`docs/architecture.drawio` + exported PNG): the 3
  services, Postgres, MinIO, client, Ingress, and communication arrows (REST
  sync call, local JWT validation).
- **Screen recording** demonstrating `docker-compose up`, register→upload→result,
  admin filter, and a walk-through of the diagram.

## Build order (each step verifiable)

1. Restructure monorepo; move `app/auth/` → `services/auth/`; extract
   `libs/shared` (settings base, JWT verify, common schemas).
2. Swap SQLite→Postgres + add Alembic to Auth; migration + superuser bootstrap.
3. Build Submissions service: models, schema, Alembic, upload endpoint + safety
   gate, MinIO integration, sqladmin admin + `/admin/submissions` filters.
4. Build Classification service: `Classifier` Protocol + `MockClassifier` +
   `/classify`; wire Submissions→Classification over `httpx`.
5. Dockerfiles per service + `docker-compose.yml` (services + Postgres + MinIO)
   + `.env.example`.
6. Tests (`pytest`) per service; `ruff` clean.
7. `deploy/k8s/` manifests; `.github/workflows/` CI/CD YAML.
8. README (arch, DB justification, safety rules what/where/why, K8s notes,
   scaling/secrets/observability), draw.io diagram, screen recording.

## Verification

- `docker-compose up` → all services healthy (`/health` green), Postgres + MinIO up.
- End-to-end: register → login (JWT set) → `POST /submissions` with a real image →
  200 with a classification result → row in `submissions` + object in MinIO.
- Safety: upload a non-image / oversized file → rejected with a clear reason.
- Admin: log in as superuser → `/admin/submissions?gender=..&country_of_origin=..&age..`
  returns filtered, paginated results; admin panel filters work.
- `ruff check` and `pytest` pass across all three services.
- Swagger (`/docs`) reachable on each service.
