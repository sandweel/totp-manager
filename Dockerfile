FROM node:20-slim AS builder

WORKDIR /build

COPY . .

WORKDIR /build/tailwindcss
RUN npm install
RUN mkdir -p ../static/css
RUN npm run build

FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    wget \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

COPY --from=builder /build/static/css/style.css ./static/css/style.css

RUN mkdir -p logs

RUN chmod +x /app/docker_entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/docker_entrypoint.sh"]
