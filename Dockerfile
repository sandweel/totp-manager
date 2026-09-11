# ---------- Tailwind build stage ----------
FROM node:20-slim AS assets

WORKDIR /build/tailwindcss
COPY tailwindcss/package.json tailwindcss/package-lock.json ./
RUN npm ci

COPY tailwindcss/ ./
COPY templates/ /build/templates/
COPY static/ /build/static/
RUN mkdir -p /build/static/css \
    && npm run build \
    && test -s /build/static/css/style.css   # fail the build if Tailwind produced nothing

# ---------- Runtime image ----------
FROM python:3.12-slim

WORKDIR /app

# asyncpg / cryptography / pillow all ship manylinux wheels: no compiler needed.
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# GeoIP database, baked in as its own layer so app code changes don't refetch it.
ARG GEOIP_URL=https://github.com/P3TERX/GeoLite.mmdb/raw/download/GeoLite2-City.mmdb
RUN mkdir -p data logs \
    && wget -q "$GEOIP_URL" -O data/GeoLite2-City.mmdb \
    && test -s data/GeoLite2-City.mmdb

COPY . .
COPY --from=assets /build/static/css/style.css ./static/css/style.css

RUN chmod +x /app/docker_entrypoint.sh \
    && addgroup --system app && adduser --system --ingroup app app \
    && chown -R app:app /app

USER app

EXPOSE 8000

ENTRYPOINT ["/app/docker_entrypoint.sh"]
