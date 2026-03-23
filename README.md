# UYTDownloader

Self-hosted YouTube download orchestration tool. Not another downloader — an orchestration product built around proven tools (yt-dlp, ffmpeg, SponsorBlock).

## What It Does

- **Probe before download** — paste a video, playlist, or channel URL and see all available entries with metadata before downloading anything
- **Select and queue** — choose which entries to download with quality/format/SponsorBlock preferences
- **Multi-stage pipeline** — each download goes through: format revalidation → download → merge → SponsorBlock → finalize
- **SponsorBlock integration** — keep, mark as chapters, or remove sponsor segments automatically
- **Archive/dedup** — tracks what you've downloaded to prevent duplicates
- **Job management** — queue, cancel, retry, monitor progress with full stage-level diagnostics
- **GPU acceleration** — NVIDIA NVENC, Apple Metal (VideoToolbox), or CPU fallback — detected automatically

## Architecture

```
Frontend (Next.js) → Backend API (FastAPI) → Queue (Celery + Redis)
                                                    ↓
                                              Worker (yt-dlp + ffmpeg)
                                                    ↓
                                              Postgres (metadata + jobs)
```

### Domain Model

```
Source → Entry → FormatSnapshot
                    ↓
               Job → JobRequest (immutable config)
                ↓
           JobStage → Artifact → ArchiveRecord
```

### Job Stages

| Stage | What it does |
|-------|-------------|
| `revalidate_formats` | Re-extract format info from YouTube |
| `download_video` | Download video stream |
| `download_audio` | Download audio stream |
| `merge` | Merge video + audio via ffmpeg |
| `sponsorblock` | Mark or remove sponsor segments |
| `finalize` | Move to output dir, checksum, archive |

## Quick Start

### Prerequisites

- Docker + Docker Compose
- (Optional) NVIDIA GPU with nvidia-docker for NVENC acceleration

### Run

```bash
git clone <repo-url> uytdownloader
cd uytdownloader
docker compose up -d
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- Health check: http://localhost:8000/health

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
    "sponsorblock_action": "remove"
  }'

# List jobs
curl http://localhost:8000/api/jobs

# Get job details (stages, artifacts)
curl http://localhost:8000/api/jobs/{job_id}

# Cancel / Retry
curl -X POST http://localhost:8000/api/jobs/{job_id}/cancel
curl -X POST http://localhost:8000/api/jobs/{job_id}/retry
```

### Sources & Entries

```bash
curl http://localhost:8000/api/sources
curl http://localhost:8000/api/sources/{source_id}/entries
curl http://localhost:8000/api/entries/{entry_id}
```

## Format Modes

| Mode | Output |
|------|--------|
| `video_audio` | Merged MP4 (video + audio) |
| `audio_only` | Audio file (webm/m4a) |
| `video_only` | Video-only file |

## Quality Presets

| Preset | yt-dlp format spec |
|--------|--------------------|
| `best` | `bestvideo+bestaudio/best` |
| `1080p` | `bestvideo[height<=1080]+bestaudio/best[height<=1080]` |
| `720p` | `bestvideo[height<=720]+bestaudio/best[height<=720]` |
| `480p` | `bestvideo[height<=480]+bestaudio/best[height<=480]` |

## GPU Acceleration

Automatically detected at runtime:

| GPU | Encoder | Detection |
|-----|---------|-----------|
| NVIDIA | `h264_nvenc` | `nvidia-smi` present |
| Apple Metal | `h264_videotoolbox` | macOS + ffmpeg encoder check |
| Intel/AMD | `h264_vaapi` | `/dev/dri/renderD128` exists |
| None | `libx264` (CPU) | Fallback |

GPU is only used for transcoding operations (SponsorBlock segment removal). Simple merges use stream copy (no re-encode needed).

## Stack

- **Frontend**: Next.js 16 + TypeScript + Tailwind CSS
- **Backend**: FastAPI + SQLAlchemy + Alembic
- **Queue**: Celery + Redis
- **Database**: PostgreSQL 16
- **Engine**: yt-dlp + deno (JS runtime) + ffmpeg
- **SponsorBlock**: Public API integration

## Development

### Local dev (without Docker)

```bash
# Backend
cd backend
pip install -e .
uvicorn app.main:app --reload

# Worker
celery -A app.celery_app:celery worker -Q probe,download --loglevel=info

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
| `downloads/` | Completed downloads |
| `work/` | In-progress downloads, staging |

## Roadmap

### V1 (Current)
- URL/playlist/channel probe + preview
- Video/audio/both download with quality selection
- Queue/download manager with stage pipeline
- ffmpeg merge + SponsorBlock mark/remove
- Archive/dedup
- GPU acceleration (NVENC/Metal/CPU)

### V1.5 (Planned)
- Channel subscriptions + auto-download
- Filter rules (ignore shorts, min/max duration, keywords)
- Compilation builder (merge multiple videos)
- Subtitle/metadata embedding
- Audio normalization

### V2 (Future)
- Browser extension handoff
- Transcript indexing + full-text search
- Background listener mode (audio-first batch)
- Mobile-friendly remote UI

## License

MIT
