# Build context is the repo root (see docker-compose.yml).
FROM python:3.12-slim

WORKDIR /srv
ENV PYTHONPATH=/srv \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY services/submissions/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY libs/shared/shared ./shared
COPY services/submissions/app ./app
COPY services/submissions/alembic.ini .
COPY services/submissions/migrations ./migrations
COPY services/submissions/entrypoint.sh .
RUN chmod +x entrypoint.sh

EXPOSE 8002
ENTRYPOINT ["./entrypoint.sh"]
