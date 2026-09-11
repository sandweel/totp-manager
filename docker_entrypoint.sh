#!/bin/sh

set -e

WORKERS="${GUNICORN_WORKERS:-1}"

# GeoIP database is baked into the image at build time. This is only a
# recovery path for a broken build / writable filesystem: it never runs
# when the file is already present (the normal case).
if [ ! -f data/GeoLite2-City.mmdb ] && [ -n "${GEOIP_URL:-}" ]; then
    echo "GeoIP database missing, downloading from GEOIP_URL..."
    wget -q "$GEOIP_URL" -O data/GeoLite2-City.mmdb \
        || echo "GeoIP download failed, continuing without location data"
fi

# Apply committed database migrations. No autogeneration at runtime.
# In Kubernetes this is done by a dedicated Job / initContainer instead,
# and RUN_MIGRATIONS=0 keeps the app container from touching the schema.
if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
    alembic upgrade head
fi

exec gunicorn main:app \
    --workers "$WORKERS" \
    --worker-class uvicorn.workers.UvicornWorker \
    --access-logfile - \
    --error-logfile - \
    --bind 0.0.0.0:8000
