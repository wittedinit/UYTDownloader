# UYTDownloader

Self-hosted YouTube download orchestration tool. Not another downloader — an orchestration product built around proven tools (yt-dlp, ffmpeg, SponsorBlock).

## What It Does

- **Probe before download** — paste a video, playlist, or channel URL and see all available entries with metadata before downloading anything
- **Select and queue** — choose which entries to download with quality/format/SponsorBlock preferences
- **Multi-stage pipeline** — each download goes through: format revalidation → download → merge → SponsorBlock → subtitle embedding → audio normalization → finalize
- **SponsorBlock integration** — keep, mark as chapters, or remove sponsor segments automatically
- **Subscriptions** — subscribe to channels/playlists with filters, auto-download new content
- **Compilation builder** — merge multiple downloaded videos into one file with chapters
- **Library** — browse, select, and download completed files from the web UI
- **Archive/dedup** — tracks what you've downloaded to prevent duplicates
- **Storage management** — retention policies and automatic disk space cleanup
- **Job management** — queue, cancel, retry, monitor real-time progress with stage-level diagnostics
- **GPU acceleration** — NVIDIA NVENC, Apple Metal (VideoToolbox), VA-API, or CPU fallback — detected automatically at runtime

## Architecture

```
Frontend (Next.js) → Backend API (FastAPI) → Queue (Celery + Redis)
                                                    ↓
                                              Worker (yt-dlp + ffmpeg)
                                                    ↓
                                         Postgres (metadata + jobs + subscriptions)
```

### Domain Model

```
Source → Entry → FormatSnapshot
Source → Subscription → SubscriptionFilter
Entry → Job → JobRequest (immutable config)
         ↓
    JobStage → Artifact → ArchiveRecord
```

### Job Stages

| Stage | What it does |
|-------|-------------|
| `revalidate_formats` | Re-extract format info from YouTube |
| `download_video` | Download video stream |
| `download_audio` | Download audio stream |
| `merge` | Merge video + audio via ffmpeg (stream copy) |
| `sponsorblock` | Mark or remove sponsor segments |
| `embed_subtitles` | Download and embed subtitle tracks (optional) |
| `normalize_audio` | EBU R128 loudness normalization (optional, two-pass) |
| `finalize` | Move to output dir, checksum, create archive record |

Stages are added dynamically based on job options. A simple audio-only download uses: revalidate → download_audio → finalize. A full video+audio with SponsorBlock removal and normalization uses all 8 stages.

## Quick Start

### Prerequisites

- Docker + Docker Compose
- (Optional) NVIDIA GPU with nvidia-docker for NVENC acceleration
- (Optional) Apple Silicon / Intel Mac for Metal (VideoToolbox) acceleration

### Run

```bash
git clone <repo-url> uytdownloader
cd uytdownloader
cp .env.example .env
docker compose up -d
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- Health check: http://localhost:8000/health

> **OrbStack users**: If `localhost:3000` doesn't work, use the container DNS:
> `http://uyt-frontend-1.orb.local:3000` and `http://uyt-backend-1.orb.local:8000`

### With GPU (NVIDIA)

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d
```

### Configuration

Environment variables (set in `.env` or docker-compose):

| Variable | Default | Description |
|----------|---------|-------------|
| `UYT_PORT` | `8000` | Backend API port |
| `UYT_FRONTEND_PORT` | `3000` | Frontend port |
| `UYT_CONCURRENCY_MODE` | `balanced` | `safe` (1 job), `balanced` (3), `power` (6) |
| `UYT_SPONSORBLOCK_DEFAULT` | `keep` | `keep`, `mark_chapters`, `remove` |
| `UYT_RETENTION` | `forever` | Auto-delete: `1_day`, `1_week`, `1_month`, `3_months`, `6_months`, `1_year`, `forever` |
| `UYT_DISK_GUARD_PCT` | `10` | Auto-cleanup when free disk space drops below this % |
| `UYT_DISK_GUARD_STRATEGY` | `oldest_first` | Cleanup order: `oldest_first`, `newest_first`, `largest_first`, `smallest_first` |
| `PUID` / `PGID` | `1000` | File ownership UID/GID |
| `TZ` | `UTC` | Timezone |

### Browser Cookies

For age-gated or member-only content, export cookies in Netscape format:

```bash
# Place your cookies file at:
config/cookies/youtube.txt
```

## API

### Probe

```bash
# Submit URL for metadata extraction
curl -X POST http://localhost:8000/api/probe \
  -H 'Content-Type: application/json' \
  -d '{"url": "https://www.youtube.com/watch?v=VIDEO_ID"}'

# Poll result
curl http://localhost:8000/api/probe/{probe_id}
```

### Jobs

```bash
# Create download jobs
curl -X POST http://localhost:8000/api/jobs \
  -H 'Content-Type: application/json' \
  -d '{
    "entry_ids": ["uuid-here"],
    "format_mode": "video_audio",
    "quality": "1080p",
    "sponsorblock_action": "remove",
    "embed_subtitles": false,
    "normalize_audio": false
  }'

# List jobs (with optional status filter)
curl http://localhost:8000/api/jobs
curl http://localhost:8000/api/jobs?status=completed

# Get job details (stages, artifacts, download URLs)
curl http://localhost:8000/api/jobs/{job_id}

# Cancel / Retry
curl -X POST http://localhost:8000/api/jobs/{job_id}/cancel
curl -X POST http://localhost:8000/api/jobs/{job_id}/retry
```

### Sources & Entries

```bash
curl http://localhost:8000/api/sources
curl http://localhost:8000/api/sources/{source_id}
curl http://localhost:8000/api/sources/{source_id}/entries
curl http://localhost:8000/api/entries/{entry_id}
```

### Subscriptions

```bash
# Create subscription for a channel/playlist
curl -X POST http://localhost:8000/api/subscriptions \
  -H 'Content-Type: application/json' \
  -d '{
    "source_id": "uuid-here",
    "check_interval_minutes": 60,
    "auto_download": true,
    "format_mode": "audio_only",
    "sponsorblock_action": "remove",
    "filters": [
      {"filter_type": "ignore_shorts"},
      {"filter_type": "min_duration", "value": "120"}
    ]
  }'

# List / Get / Update / Delete
curl http://localhost:8000/api/subscriptions
curl http://localhost:8000/api/subscriptions/{sub_id}
curl -X PATCH http://localhost:8000/api/subscriptions/{sub_id} \
  -H 'Content-Type: application/json' -d '{"enabled": false}'
curl -X DELETE http://localhost:8000/api/subscriptions/{sub_id}

# Manually trigger a check
curl -X POST http://localhost:8000/api/subscriptions/{sub_id}/check
```

### Compilations

```bash
# Merge multiple downloaded entries into one file
curl -X POST http://localhost:8000/api/compilations \
  -H 'Content-Type: application/json' \
  -d '{
    "items": [
      {"entry_id": "uuid-1", "position": 0},
      {"entry_id": "uuid-2", "position": 1}
    ],
    "mode": "video_chapters",
    "title": "My Compilation",
    "normalize_audio": false
  }'
```

Compilation modes: `video_chapters`, `video_no_chapters`, `audio_chapters`, `audio_no_chapters`

### Library

```bash
# List all downloaded files
curl http://localhost:8000/api/library

# Download a specific file
curl -O http://localhost:8000/api/library/download/{filename}

# Delete a file
curl -X DELETE http://localhost:8000/api/library/{filename}
```

### Storage Management

```bash
# Get disk usage stats
curl http://localhost:8000/api/storage/usage

# Get available presets
curl http://localhost:8000/api/storage/presets

# Preview retention cleanup (dry run)
curl -X POST "http://localhost:8000/api/storage/retention?retention=1_week&dry_run=true"

# Run retention cleanup
curl -X POST "http://localhost:8000/api/storage/retention?retention=1_week"

# Preview disk guard cleanup
curl -X POST "http://localhost:8000/api/storage/disk-guard?min_free_pct=10&strategy=oldest_first&dry_run=true"

# Run disk guard cleanup
curl -X POST "http://localhost:8000/api/storage/disk-guard?min_free_pct=10&strategy=largest_first"
```

## Format Modes

| Mode | Output |
|------|--------|
| `video_audio` | Merged MP4 (video + audio) |
| `audio_only` | Audio file (M4A) |
| `video_only` | Video-only file |

## Quality Presets

| Preset | yt-dlp format spec |
|--------|--------------------|
| `best` | `bestvideo+bestaudio/best` |
| `2160p` | `bestvideo[height<=2160]+bestaudio/best[height<=2160]` |
| `1080p` | `bestvideo[height<=1080]+bestaudio/best[height<=1080]` |
| `720p` | `bestvideo[height<=720]+bestaudio/best[height<=720]` |
| `480p` | `bestvideo[height<=480]+bestaudio/best[height<=480]` |

## Subscription Filters

| Filter | Description |
|--------|-------------|
| `ignore_shorts` | Skip videos shorter than 60 seconds |
| `ignore_live` | Skip live streams and was-live content |
| `min_duration` | Minimum duration in seconds (value required) |
| `max_duration` | Maximum duration in seconds (value required) |
| `keyword_include` | Only download if title contains keyword |
| `keyword_exclude` | Skip if title contains keyword |

## GPU Acceleration

Automatically detected at runtime (priority: NVIDIA → Apple → VA-API → CPU):

| GPU | Encoder | Detection |
|-----|---------|-----------|
| NVIDIA | `h264_nvenc` | `nvidia-smi` present |
| Apple Metal | `h264_videotoolbox` | macOS + ffmpeg encoder check |
| Intel/AMD | `h264_vaapi` | `/dev/dri/renderD128` exists |
| None | `libx264` (CPU) | Fallback |

GPU is used for transcoding operations: SponsorBlock segment removal, audio normalization, compilation re-encoding, and subtitle embedding when re-encode is needed. Simple video+audio merges use stream copy (no re-encode, no GPU needed).

## Stack

- **Frontend**: Next.js 16 + TypeScript + Tailwind CSS
- **Backend**: FastAPI + SQLAlchemy + Alembic
- **Queue**: Celery + Redis + Celery Beat (scheduler)
- **Database**: PostgreSQL 16
- **Engine**: yt-dlp + deno (JS runtime) + ffmpeg
- **SponsorBlock**: Public API integration (sponsor.ajay.app)

## Docker Services

| Service | Image | Purpose |
|---------|-------|---------|
| `postgres` | postgres:16-alpine | Database |
| `redis` | redis:7-alpine | Queue broker + result backend |
| `backend` | uyt-backend | FastAPI API server |
| `worker` | uyt-worker | Celery worker (downloads, processing) |
| `beat` | uyt-beat | Celery Beat (subscription scheduler, storage cleanup) |
| `frontend` | uyt-frontend | Next.js web UI |

## Development

### Local dev (without Docker)

```bash
# Backend
cd backend
pip install -e .
uvicorn app.main:app --reload

# Worker
celery -A app.celery_app:celery worker -Q probe,download --loglevel=info

# Beat (subscription scheduler)
celery -A app.celery_app:celery beat --loglevel=info

# Frontend
cd frontend
npm install
npm run dev
```

### Database migrations

```bash
# Generate migration
docker compose exec backend bash -c "PYTHONPATH=/app alembic revision --autogenerate -m 'description'"

# Apply
docker compose exec backend bash -c "PYTHONPATH=/app alembic upgrade head"
```

## Volumes

| Path | Purpose |
|------|---------|
| `config/` | Cookies, logs, job logs |
| `downloads/` | Completed downloads (served via Library API) |
| `work/` | In-progress downloads, staging |

## Roadmap

### V1 + V1.5 (Current)
- URL/playlist/channel probe + preview
- Video/audio/both download with quality selection (480p to 4K)
- Queue/download manager with 8-stage pipeline
- ffmpeg merge + SponsorBlock mark/remove
- Subtitle embedding + audio normalization
- Archive/dedup
- GPU acceleration (NVENC/Metal/VA-API/CPU)
- Channel subscriptions + auto-download with filters
- Compilation builder (merge multiple videos with chapters)
- Library browser with file download
- Storage management (retention + disk guard)
- Real-time progress tracking

### V2 (Future)
- Browser extension handoff
- Transcript indexing + full-text search
- Background listener mode (audio-first batch)
- Output profiles (Plex-compatible, podcast-friendly)
- Mobile-friendly remote UI

## License

MIT
