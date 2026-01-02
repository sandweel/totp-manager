#!/bin/bash

set -e

# Default database configuration
MYSQL_ROOT_PASSWORD="${MYSQL_ROOT_PASSWORD:-rootpassword}"
MYSQL_DATABASE="${MYSQL_DATABASE:-totp_manager}"
MYSQL_USER="${MYSQL_USER:-totp_user}"
MYSQL_PASSWORD="${MYSQL_PASSWORD:-totp_password}"

# Set DATABASE_URL if not provided
if [ -z "$DATABASE_URL" ]; then
    export DATABASE_URL="mysql+asyncmy://${MYSQL_USER}:${MYSQL_PASSWORD}@localhost:3306/${MYSQL_DATABASE}"
fi

# Cleanup function
cleanup() {
    echo "Shutting down gracefully..."
    # Stop Gunicorn workers
    pkill -TERM -f "gunicorn main:app" 2>/dev/null || true
    sleep 2
    # Stop MariaDB gracefully
    mysqladmin shutdown 2>/dev/null || true
    sleep 1
    # Force kill if still running
    pkill -9 -f "mariadbd\|mysqld\|mariadbd-safe\|mysqld_safe" 2>/dev/null || true
    exit 0
}

trap cleanup SIGTERM SIGINT

echo "Starting MariaDB server..."

# Initialize MariaDB data directory if needed
if [ ! -d "/var/lib/mysql/mysql" ]; then
    echo "Initializing MariaDB data directory..."
    mysql_install_db --datadir=/var/lib/mysql --user=mysql --skip-name-resolve
fi

# Clean up any stale lock/pid files
rm -f /var/lib/mysql/*.pid /var/run/mysqld/mysqld.pid 2>/dev/null || true

# Start MariaDB in background (use mariadbd-safe if available, otherwise mysqld_safe)
echo "Starting MariaDB..."
if command -v mariadbd-safe &> /dev/null; then
    mariadbd-safe --datadir=/var/lib/mysql --user=mysql --skip-networking=0 --bind-address=0.0.0.0 --skip-name-resolve &
else
    mysqld_safe --datadir=/var/lib/mysql --user=mysql --skip-networking=0 --bind-address=0.0.0.0 --skip-name-resolve &
fi

MYSQLD_PID=$!

# Wait for MariaDB to be ready
echo "Waiting for MariaDB to be ready..."
for i in {30..0}; do
    if mysqladmin ping -h localhost --silent 2>/dev/null; then
        break
    fi
    # Check if process is still alive
    if ! kill -0 $MYSQLD_PID 2>/dev/null; then
        echo "MariaDB process died!"
        exit 1
    fi
    echo "MariaDB is not ready yet, waiting... ($i seconds remaining)"
    sleep 1
done

if [ $i -eq 0 ]; then
    echo "MariaDB failed to start!"
    kill $MYSQLD_PID 2>/dev/null || true
    exit 1
fi

echo "MariaDB is ready!"

# Create database and user if they don't exist
echo "Setting up database..."
mysql -u root <<EOF 2>/dev/null || true
CREATE DATABASE IF NOT EXISTS ${MYSQL_DATABASE} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS '${MYSQL_USER}'@'%' IDENTIFIED BY '${MYSQL_PASSWORD}';
GRANT ALL PRIVILEGES ON ${MYSQL_DATABASE}.* TO '${MYSQL_USER}'@'%';
FLUSH PRIVILEGES;
EOF

# Set root password if provided
if [ -n "$MYSQL_ROOT_PASSWORD" ] && [ "$MYSQL_ROOT_PASSWORD" != "rootpassword" ]; then
    mysql -u root <<EOF 2>/dev/null || true
SET PASSWORD FOR 'root'@'localhost' = PASSWORD('${MYSQL_ROOT_PASSWORD}');
FLUSH PRIVILEGES;
EOF
fi

echo "Database setup complete!"

# Run migrations
echo "Running database migrations..."
cd /app
if ! mysql $MYSQL_DATABASE -uroot -p$MYSQL_ROOT_PASSWORD -e "SHOW TABLES LIKE 'alembic_version';" | grep -q "alembic_version"; then
    mkdir alembic/versions
    alembic revision --autogenerate -m "initial migration"
    alembic upgrade head
else
    echo "Migrations already exist!"
fi

echo "Migrations complete!"

# Start application (don't use exec so trap works)
echo "Starting application..."
WORKERS="${GUNICORN_WORKERS:-1}"
gunicorn main:app --workers "$WORKERS" --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 &
GUNICORN_PID=$!

# Wait for Gunicorn process (this will block until it exits)
wait $GUNICORN_PID
