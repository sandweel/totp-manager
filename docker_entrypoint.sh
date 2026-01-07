#!/bin/sh

set -e

WORKERS="${GUNICORN_WORKERS:-1}"

# Run initial database migration
python docker_initial_migration.py

# Download MaxMind GeoIP database
wget https://github.com/P3TERX/GeoLite.mmdb/raw/download/GeoLite2-City.mmdb -O data/GeoLite2-City.mmdb

exec gunicorn main:app --workers "$WORKERS" --worker-class uvicorn.workers.UvicornWorker --access-logfile - --error-logfile - --bind 0.0.0.0:8000
