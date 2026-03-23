#!/bin/bash
set -e

PUID=${PUID:-1000}
PGID=${PGID:-1000}

# Create app user if not root
if [ "$(id -u)" = "0" ]; then
    groupadd -g "$PGID" -o appgroup 2>/dev/null || true
    useradd -u "$PUID" -g "$PGID" -o -s /bin/bash -d /app appuser 2>/dev/null || true

    # Ensure runtime directories exist and are owned correctly
    mkdir -p /config/logs/jobs /config/cookies /downloads /work/incomplete /work/staging
    chown -R "$PUID:$PGID" /config /downloads /work

    # Run migrations as app user
    PYTHONPATH=/app gosu appuser alembic upgrade head 2>/dev/null || echo "Migration skipped (DB may not be ready yet)"

    # Start as app user
    exec gosu appuser uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
else
    mkdir -p /config/logs/jobs /config/cookies /downloads /work/incomplete /work/staging
    PYTHONPATH=/app alembic upgrade head 2>/dev/null || echo "Migration skipped"
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
fi
