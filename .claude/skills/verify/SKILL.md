---
name: verify
description: Build/launch/drive recipe for verifying changes to the photo-classification platform locally (no Docker needed).
---

# Verifying photo_classification locally

Three FastAPI services; all run from the repo venv with SQLite fallback — no
Postgres/Docker required. `SECRET` must be ≥32 chars and identical across
services (shared JWT verification).

## Launch

**FIRST check whether the user's own dev servers are already running** —
they launch them from VSCode (`.vscode/launch.json`, uvicorn `--reload`, CWD
`services/<name>`, default SQLite DBs `services/*/{auth,submissions}.db`,
storage `services/submissions/uploads`). `lsof -nP -i :8001 -i :8002 -i :8003`
and inspect the command line. If theirs are up: verify against them (reload
already picked up code edits; templates reload per-request), create only your
own test rows and delete them after, and NEVER kill those processes.

Launching yourself requires `PYTHONPATH` to include `libs/shared`, or imports
fail with `ModuleNotFoundError: No module named 'shared'` — and uvicorn still
occupies/fails the port silently in the background. Always check the launch
logs before trusting a green /health (it may be someone else's server).

```bash
export PYTHONPATH=$PWD/libs/shared
export SECRET="local-verify-secret-at-least-32-chars-long"
V=$PWD/venv/bin; TMP=<scratch dir>; mkdir -p $TMP/uploads
(cd services/classification && $V/uvicorn app.main:app --port 8003 &)
(cd services/submissions && DATABASE_URL="sqlite+aiosqlite:///$TMP/submissions.db" \
  STORAGE_LOCAL_DIR=$TMP/uploads $V/uvicorn app.main:app --port 8002 &)
(cd services/auth && DATABASE_URL="sqlite+aiosqlite:///$TMP/auth.db" \
  $V/uvicorn app.main:app --port 8001 &)
# wait for GET /health == 200 on all three ports
```

## Drive the browser flow (curl + cookie jar)

```bash
curl -X POST localhost:8001/auth/register -H 'Content-Type: application/json' \
  -d '{"email":"pb@test.io","password":"secret123"}'          # 201
curl -c cookies.txt -X POST localhost:8001/login \
  -d 'email=pb@test.io&password=secret123'                    # 303 + photoauth cookie
curl -b cookies.txt localhost:8001/                           # home page HTML
curl -b cookies.txt -X POST localhost:8002/upload \
  -F "image=@test_uploads/<any>.png;type=image/png" -F "name=Ana" -F "age=31" \
  -F "place_of_living=Zagreb" -F "gender=female" -F "country_of_origin=Croatia"  # 200
```

The `photoauth` cookie works across all localhost ports (host-scoped).

## Gotchas

- Tests: `cd services/<name> && ../../venv/bin/python -m pytest tests/ -q`
  (conftest sets its own SECRET/DB). Lint: `venv/bin/ruff check`.
- Screenshots: save the rendered page HTML (CSS is fully inline) and render it
  with headless Chrome: `"/Applications/Google Chrome.app/Contents/MacOS/Google
  Chrome" --headless --screenshot=out.png --window-size=1440,900 page.html`.
  Thumbnail `<img>` URLs need the auth cookie, so swap their `src` to a local
  file first. Chrome ignores `--window-size` below ~500px wide (layout renders
  at the minimum and the screenshot crops) — don't trust sub-500px shots.
- Kill services by port (`kill $(lsof -ti :8001)`), pkill by pattern is
  unreliable for the venv uvicorn processes.
