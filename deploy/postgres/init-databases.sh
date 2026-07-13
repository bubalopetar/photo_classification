#!/bin/sh
# Create one database per service (database-per-service pattern). Runs once, on
# first Postgres startup, via docker-entrypoint-initdb.d.
set -e

# --dbname is required: without it psql connects to a database named after
# the user, which doesn't exist (compose sets POSTGRES_DB=postgres).
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE DATABASE auth;
    CREATE DATABASE submissions;
EOSQL
