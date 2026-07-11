#!/bin/sh
set -e
# Apply migrations before serving. On a fresh database this creates the schema;
# on an up-to-date one it is a no-op.
alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port 8001
