FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    ca-certificates \
    tini \
    gosu \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Install deno for yt-dlp JS runtime (required for YouTube extraction)
RUN ARCH=$(uname -m) && \
    curl -fsSL -L "https://github.com/denoland/deno/releases/latest/download/deno-${ARCH}-unknown-linux-gnu.zip" -o /tmp/deno.zip && \
    unzip -o /tmp/deno.zip -d /usr/local/bin/ && \
    chmod +x /usr/local/bin/deno && \
    rm /tmp/deno.zip

WORKDIR /app

COPY backend/pyproject.toml .
RUN pip install --no-cache-dir -e . 2>/dev/null || pip install --no-cache-dir .

COPY backend/ .

COPY docker/entrypoints/worker.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["tini", "--", "/entrypoint.sh"]
