# Build context is the repo root (see docker-compose.yml) so the image can copy
# both this service and the shared library.
FROM python:3.12-slim

WORKDIR /srv
ENV PYTHONPATH=/srv \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY services/auth/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY libs/shared/shared ./shared
COPY services/auth/app ./app
COPY services/auth/alembic.ini .
COPY services/auth/migrations ./migrations
COPY services/auth/entrypoint.sh .
RUN chmod +x entrypoint.sh

EXPOSE 8001
ENTRYPOINT ["./entrypoint.sh"]
