#!/bin/sh
# Create one database per service (database-per-service pattern). Runs once, on
# first Postgres startup, via docker-entrypoint-initdb.d.
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
    CREATE DATABASE auth;
    CREATE DATABASE submissions;
EOSQL
