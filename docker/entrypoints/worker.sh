#!/bin/bash
set -e

PUID=${PUID:-1000}
PGID=${PGID:-1000}

# Concurrency based on mode
case "${UYT_CONCURRENCY_MODE:-balanced}" in
    safe)     CONCURRENCY=1 ;;
    balanced) CONCURRENCY=3 ;;
    power)    CONCURRENCY=6 ;;
    *)        CONCURRENCY=3 ;;
esac

if [ "$(id -u)" = "0" ]; then
    groupadd -g "$PGID" -o appgroup 2>/dev/null || true
    useradd -u "$PUID" -g "$PGID" -o -s /bin/bash -d /app appuser 2>/dev/null || true

    mkdir -p /config/logs/jobs /config/cookies /downloads /work/incomplete /work/staging
    chown -R "$PUID:$PGID" /config /downloads /work

    exec gosu appuser celery -A app.celery_app:celery worker \
        --loglevel=info \
        --concurrency="$CONCURRENCY" \
        -Q probe,download
else
    mkdir -p /config/logs/jobs /config/cookies /downloads /work/incomplete /work/staging
    exec celery -A app.celery_app:celery worker \
        --loglevel=info \
        --concurrency="$CONCURRENCY" \
        -Q probe,download
fi
