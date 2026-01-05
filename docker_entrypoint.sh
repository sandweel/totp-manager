#!/bin/sh

set -e

WORKERS="${GUNICORN_WORKERS:-1}"

python docker_initial_migration.py

exec gunicorn main:app --workers "$WORKERS" --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
