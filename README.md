# Photo Classification Platform

A cloud-deployable, web-based platform where users register, log in, upload a
photo with metadata, and receive a classification result; and admins filter,
search and inspect submissions. Built as **three containerized microservices**
in one monorepo, orchestrated locally with Docker Compose.

```
Browser / API client
        │
        ├──────────────► Auth service (8001)          ── users, register/login, JWT
        │                     │ owns
        │                     ▼
        │                 PostgreSQL: auth db
        │
        └──────────────► Submissions service (8002)    ── upload, metadata, admin panel
                              │ owns          │
                              ▼               ├─► photo volume (local disk)
                          PostgreSQL:         │
                          submissions db      └─► Classification service (8003)  ── classify + safety
```

See [docs/architecture.drawio](docs/architecture.drawio) (editable) and
[docs/architecture.svg](docs/architecture.svg) (viewable) for the full block
diagram.

---

## Why microservices, and why these three

| Service | Responsibility | Owns |
|---|---|---|
| **auth** | Registration, login, JWT issuing, user admin | `users` DB |
| **submissions** | Photo upload, metadata, admin filter/search, admin panel | `submissions` DB + photo volume |
| **classification** | Image classification + content-safety verdict | nothing (stateless) |

The split is by **bounded context**, and classification is a service (not a
module) for a concrete reason: it has a different scaling and resource profile
(CPU/GPU-bound inference) from the I/O-bound web services, so it scales
independently. Auth is isolated because identity is a natural trust boundary.

**Communication**
- Clients talk REST/JSON to Auth and Submissions (both also serve minimal HTML).
- Submissions → Classification is a **synchronous HTTP** call on upload, so the
  result is returned immediately.
- **Auth is not on the request hot path.** Each service verifies JWTs *locally*
  using the shared `SECRET` (see `libs/shared/shared/security.py`); Auth adds
  `email` and `is_superuser` claims so downstream services can authorize
  (including admin-only routes) without a network call back to Auth. The one
  exception is the Submissions admin **panel** login, which exchanges
  credentials with Auth once, at login.

---

## Repository layout

```
services/
  auth/            FastAPI · fastapi-users · sqladmin · Alembic
  submissions/     FastAPI · sqladmin · Alembic · Pillow · httpx
  classification/  FastAPI · MediaPipe (EfficientNet-Lite0)
libs/shared/       JWT verify/encode, base settings, health probes, JSON logging,
                   cross-service contracts (ClassificationResult)
deploy/postgres/   one-time DB-per-service init script
docs/              architecture diagram + design specs
docker-compose.yml
.env.example
```

Each service is a self-contained image with its own `requirements.txt`,
`Dockerfile`, and (where stateful) `migrations/`. The build context is the repo
root so each image can copy both its own code and `libs/shared`.

---

## Quick start (Docker Compose)

```bash
cp .env.example .env            # then edit SECRET
docker compose up --build
```

This starts PostgreSQL and all three services. A superuser
(`ADMIN_EMAIL` / `ADMIN_PASSWORD` from `.env`) is created on first boot.

| URL | What |
|---|---|
| http://localhost:8001 | Auth — register / login / home |
| http://localhost:8001/docs | Auth API (Swagger) |
| http://localhost:8002/upload | Upload a photo (browser) |
| http://localhost:8002/my | My submissions (browser) |
| http://localhost:8002/docs | Submissions API (Swagger) |
| http://localhost:8002/admin | Submissions admin panel (superuser) |
| http://localhost:8001/admin | Users admin panel (superuser) |
| http://localhost:8003/docs | Classification API (Swagger) |

**User journey:** open `:8001`, register → you're redirected home → *Upload a
photo* → fill the form and submit → the classification result is shown → your
photo lives on the photo volume, its metadata + result in Postgres.

---

## Local development (no Docker)

Each service defaults to **SQLite** and a local uploads directory, so it runs
with zero infrastructure. From a service directory, with the shared lib on the
path:

```bash
cd services/auth
PYTHONPATH=".:../../libs/shared" SECRET=dev-secret-please-change \
  uvicorn app.main:app --reload --port 8001
```

Do the same for `submissions` (port 8002) and `classification` (port 8003). VS
Code launch configs for all three are in `.vscode/launch.json`.

---

## API endpoints

**Auth** (`:8001`) — provided by fastapi-users:
- `POST /auth/register` · `POST /auth/jwt/login` · `POST /auth/jwt/logout`
- `GET /users/me` · `GET|POST /login` · `GET|POST /register` · `GET /logout`

**Submissions** (`:8002`):
- `POST /submissions` — multipart: photo + `name, age, place_of_living, gender, country_of_origin, description?` → returns the stored record incl. classification
- `GET /submissions/me` — the caller's submissions
- `GET /submissions/{id}` — one record (owner or admin)
- `GET /submissions/{id}/photo` — the stored image (owner or admin)
- `GET /admin/submissions` — **admin only**; filters: `gender`, `country_of_origin`, `place_of_living`, `age_min`, `age_max`, `q` (name search), `limit`, `offset`
- `GET /upload` — browser upload form
- `GET /my` — browser view of the caller's submissions (thumbnails, classification, timestamps)

**Classification** (`:8003`):
- `POST /classify` — image → `{category, confidence, safe, reasons}`

Every service also exposes `GET /health` (liveness) and `GET /ready`
(readiness — checks the DB where applicable). Full request/response schemas are
in each service's `/docs`.

---

## Database

**PostgreSQL** was chosen over a document store because the data is relational
and the admin workload is filter/range queries over structured columns
(age ranges, gender, location, country) — exactly what a relational engine with
btree indexes serves well, with ACID guarantees for writes.

- **Database-per-service**: Auth owns `auth`, Submissions owns `submissions`
  (separate databases on one instance here; separable to distinct instances
  later). There is deliberately **no cross-database FK** on `submission.user_id`
  — integrity is enforced at the app layer via the verified JWT.
- **Schema** (`submission`): `id`, `user_id`, `name`, `age`, `place_of_living`,
  `gender`, `country_of_origin`, `description?`, `photo_key`,
  `photo_content_type`, `classification` (JSON), `created_at`, `updated_at`.
- **Indexing**: btree indexes on every admin-filter column
  (`age`, `gender`, `place_of_living`, `country_of_origin`), plus `user_id` and
  `created_at`. See `services/submissions/migrations/versions/0001_initial.py`.
- **Migrations**: Alembic per stateful service (async env, driver-agnostic).
  Containers run `alembic upgrade head` on startup (`entrypoint.sh`). The local
  SQLite path uses `create_all` as a convenience fallback.

**Photo storage**: photo bytes are written to a **local directory** (a named
Docker volume in compose, `STORAGE_LOCAL_DIR`); the database stores only the
object key, never the bytes. The `Storage` protocol in
`services/submissions/app/storage.py` is the seam a cloud backend (S3 / GCS /
MinIO) plugs into for production — implement `put`/`get` and change one line in
`get_storage()`; nothing else in the service changes.

---

## Security & safety rules

Documented as **what / where / why**:

| Rule | Where | Why |
|---|---|---|
| JWT bearer + http-only cookie auth | `libs/shared/security.py`, auth `backends.py` | Stateless auth; cookie isn't script-readable (XSS). |
| Passwords hashed (argon2/bcrypt via fastapi-users) | auth `manager.py` | Never store plaintext. |
| Admin-only RBAC on `/admin/*` | submissions `security.py`, `admin.py` | Only superusers see all submissions. |
| Local JWT verification (shared secret, audience, expiry) | `libs/shared/security.py` | No trust in unverified input; no chatty auth calls. |
| Max upload size | submissions `safety.py` | Reject DoS / storage-abuse payloads. |
| **Magic-byte** content sniffing (not the client header) | submissions `safety.py` | Client `Content-Type` is trivially spoofed. |
| Allow-list of image types | submissions `safety.py` | Only decode formats we intend to. |
| Image-dimension cap | submissions `safety.py` | Reject decompression bombs. |
| **EXIF stripping** (re-encode via Pillow) | submissions `safety.py` | Remove GPS/device metadata (privacy). |
| Server-generated UUID object keys | submissions `storage.py` | Malicious filenames can't traverse paths / collide. |
| Content-safety gate | classification `classifier.py` → submissions `service.py` | Unsafe images (`safe=false`) are rejected (422) with the reason. |
| Input validation (age range, gender enum, length caps) | submissions `schemas.py` | Reject malformed metadata early. |
| **Password policy** (min 8 chars, must not contain the e-mail) | auth `manager.py` (`validate_password`) | Enforced by fastapi-users on register, reset and update — every path that sets a password; blocks trivially guessable credentials. |
| **Rate limiting, per client IP** — login 10/min, register 5/min (auth); upload 20/min (submissions) | `libs/shared/ratelimit.py`, wired in each service's `limits.py` | Damps credential brute-force, bulk account creation, and upload abuse (uploads fan out into classification + storage). JSON and browser variants of an endpoint share one bucket so the limit can't be bypassed by alternating; limited clients get `429` + `Retry-After`. In-memory per replica by design — see the module docstring for the Redis upgrade path. Budgets/window tunable via `LOGIN_RATE_LIMIT`, `REGISTER_RATE_LIMIT`, `UPLOAD_RATE_LIMIT`, `RATE_LIMIT_WINDOW_SECONDS`; kill switch `RATE_LIMIT_ENABLED=false`. |
| **CORS deny-by-default** (explicit origin allow-list via `CORS_ALLOW_ORIGINS`) | `libs/shared/cors.py`, wired in auth & submissions `main.py` | The UI is server-rendered same-origin, so no cross-origin browser access is needed — and none is granted. When a SPA frontend appears, its origin is opted in by env var; wildcard is unsupported because credentialed requests (our cookie auth) + `*` is invalid anyway. Classification deliberately has no CORS: it's internal-only and never exposed to browsers. |
| Secrets via env / secret store, never in code | all `config.py`, `.env` (git-ignored) | Keep credentials out of the repo/image. |

---

## Classification (real model)

`services/classification/app/classifier.py` runs
[MediaPipe's image classifier](https://developers.google.com/edge/mediapipe/solutions/vision/image_classifier/python)
with **EfficientNet-Lite0** (ImageNet, 1000 labels) on CPU, ~20 ms per image.
The Docker image downloads the model weights at build time; for a bare-python
run, download them once:

```bash
curl -L -o services/classification/models/efficientnet_lite0.tflite \
  https://storage.googleapis.com/mediapipe-models/image_classifier/efficientnet_lite0/float32/latest/efficientnet_lite0.tflite
```

**Content safety:** if any top label matches a weapon-related keyword
(`rifle`, `revolver`, `pistol`, ...) above a confidence threshold, the image is
flagged unsafe and Submissions rejects the upload with the reason.

Inference runs in a threadpool (CPU-bound work stays off the event loop) behind
a lock (MediaPipe task objects aren't documented as thread-safe). The
`Classifier` protocol is the seam for swapping in a different model
(torchvision / ONNX / a hosted API): implement `classify` and change one line
in `main.py`; the API contract (`shared/contracts.py`) and the Submissions
integration are unchanged.

---

## Testing & linting

```bash
# per service (from the service dir)
cd services/submissions && PYTHONPATH=".:../../libs/shared" pytest -q
# lint the whole repo
ruff check services libs
```

60 tests cover: JWT round-trip/claims, auth register/login, the password
policy, rate limiting (the sliding-window limiter plus the 429 behaviour of
login/register/upload), CORS (deny-by-default and the origin allow-list),
the safety gate (incl. EXIF stripping and
spoofed-type rejection), the upload workflow, the browser pages and admin
thumbnails, admin RBAC and every filter, and the MediaPipe classifier (the
classification tests auto-skip if the model file hasn't been downloaded —
the Docker image always ships it).

---

## CI/CD

`.github/workflows/ci.yml` runs on every push to `main` and on pull requests:

1. **lint** — `ruff check services libs` (config in `pyproject.toml`).
2. **test** — installs all three services' pinned requirements into one
   environment (the pins are consistent across services), downloads the
   EfficientNet-Lite0 weights so the classification tests actually run instead
   of auto-skipping, then runs `pytest` per package exactly as in
   "Testing & linting" above.
3. **build-and-push** — a matrix job over `auth` / `submissions` /
   `classification` builds each Docker image (repo root as build context, same
   command as local: `docker build -f services/<svc>/Dockerfile .`). On `main`
   the images are pushed to Docker Hub as
   `<user>/photo-<svc>:latest` and `<user>/photo-<svc>:<git sha>`; PR builds
   only verify the image builds. Layer caching goes through the GitHub Actions
   cache.

Pushing requires two repository secrets: `DOCKERHUB_USERNAME` and
`DOCKERHUB_TOKEN` (a Docker Hub access token with Read & Write scope).

**Deployment step — documented, not implemented.** There is no target cluster
for this assessment, so the pipeline stops after pushing images. The deploy
job would: run on `main` after `build-and-push`, authenticate to the cluster
via a `KUBECONFIG` secret (or a cloud OIDC role), substitute the freshly
pushed `:<git sha>` tag into the manifests (kustomize `images:` or Helm
`--set image.tag=`), and `kubectl apply` / `helm upgrade --install` followed
by `kubectl rollout status` per Deployment so a failed rollout fails the
pipeline.

---

## Kubernetes strategy

No manifests ship with this iteration; this section is the concrete plan.

**Topology.** One Deployment + ClusterIP Service per microservice. An Ingress
routes external traffic to `auth` and `submissions` only; `classification`
stays cluster-internal — nothing outside ever needs it, which shrinks the
attack surface for the one service that parses untrusted image bytes.

```yaml
# shape of each service (illustrative, not a complete manifest)
apiVersion: apps/v1
kind: Deployment
metadata: { name: submissions }
spec:
  replicas: 2
  template:
    spec:
      containers:
        - name: submissions
          image: <user>/photo-submissions:<git sha>   # set by CI
          envFrom:
            - configMapRef: { name: submissions-config }
            - secretRef:    { name: platform-secrets }
          livenessProbe:  { httpGet: { path: /health, port: 8002 } }
          readinessProbe: { httpGet: { path: /ready,  port: 8002 } }
```

**Scaling.** `classification` gets a HorizontalPodAutoscaler on CPU — its
inference is CPU-bound and its independent scaling is the payoff of splitting
it out. `auth` and `submissions` run ≥2 replicas for availability. One caveat
when replicating: the rate limiter is in-memory per pod, so N replicas
multiply the effective limit by N — production would move the counters to
Redis (the `RateLimiter` seam in `libs/shared/shared/ratelimit.py`) or pin
clients with session affinity.

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
spec:
  scaleTargetRef: { apiVersion: apps/v1, kind: Deployment, name: classification }
  minReplicas: 1
  maxReplicas: 6
  metrics:
    - type: Resource
      resource: { name: cpu, target: { type: Utilization, averageUtilization: 70 } }
```

**Secrets & config.** `SECRET` (the shared JWT key), database credentials, and
the bootstrap admin credentials live in Kubernetes Secrets — in a real cluster
sourced from a manager (External Secrets Operator / SOPS / cloud secret
stores), never committed. Everything non-sensitive (service URLs, rate-limit
knobs, CORS allow-list) is a ConfigMap. Postgres itself would be a managed
service (RDS / Cloud SQL) rather than an in-cluster pod.

**Storage.** Short-term, uploaded photos go on a PersistentVolumeClaim mounted
at `STORAGE_LOCAL_DIR` (`ReadWriteMany` once `submissions` has >1 replica).
The real answer is object storage: implement the three-method `Storage`
protocol in `services/submissions/app/storage.py` against S3/GCS and swap it
in — nothing else changes.

**Observability.** Liveness/readiness probes are already served by every
service (`/health`, `/ready` from `libs/shared/shared/health.py`). Logs go to
stdout for the cluster log pipeline (structured JSON via
`libs/shared/shared/logging.py`); next steps would be a Prometheus `/metrics`
endpoint per service (request rate/latency/429s, classification inference
time) and trace propagation between `submissions` and `classification`.
