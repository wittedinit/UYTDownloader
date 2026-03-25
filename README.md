# UYTDownloader

Self-hosted Ultimate YouTube download orchestration tool. Built around yt-dlp, ffmpeg, and SponsorBlock — not another downloader, but a complete management platform for offline YouTube consumption.

## Features

### Download
- **Probe before download** — paste any video, playlist, or channel URL. See titles, thumbnails, channel, duration, and upload dates before committing
- **Video + Audio, Audio Only, or Video Only** output modes
- **Quality selection** — Best Available, 2160p (4K), 1080p, 720p, 480p for video; 320/256/192/128/64 kbps for audio
- **Output format conversion** — MP4/H.264, MP4/H.265, MKV, WebM/VP9 for video; MP3, M4A/AAC, Opus, FLAC for audio
- **Video bitrate control** — Auto, 8000/5000/3000/1500/800 kbps with quality/size recommendations
- **SponsorBlock** — keep all, mark as chapters, or remove sponsor segments automatically
- **Subtitle embedding** and **audio normalization** (EBU R128 two-pass) as optional post-processing stages
- **Real-time progress** — live percentage and speed displayed during downloads
- **Archive/dedup** — tracks downloads to prevent re-downloading the same content
- **Reset** — clear current probe results and start fresh without reloading the page

### Jobs
- **Real-time monitoring** — progress bars, speed, ETA for active downloads
- **Download artifacts** — completed jobs show download links for their output files
- **Cancel / Retry / Delete** — single job or bulk actions
- **Bulk retry** — retry all failed jobs at once with one click
- **Source file tracking** — jobs show when their output file has been deleted from the library

### Merge & Compile
- **Download & Merge** — download multiple playlist/channel entries and merge into one file with chapter markers
- **Library Merge** — select files in the Library and merge them post-download
- **Drag-and-drop reordering** — set merge order by dragging entries in the list
- **4 compilation modes** — video with chapters, video without, audio with chapters, audio without

### Library
- **Browse all downloads** — file list with type icons, sizes, dates
- **Select & Download** — individual or bulk download via browser; option to zip all selected (store mode) into a single download
- **Select & Delete** — bulk file cleanup
- **Select & Merge** — combine downloaded files into compilations

### Subscriptions
- **Subscribe to channels/playlists** — auto-check for new content on a configurable interval
- **Filters** — ignore shorts (<60s), ignore live, min/max duration, keyword include/exclude
- **Auto-download** — new entries matching filters are queued automatically
- **Celery Beat scheduler** — checks all due subscriptions every 5 minutes

### Storage Management
- **Disk usage dashboard** — total/used/free space, download count and size
- **Retention policy** — auto-delete files older than: 1 day, 1 week, 1 month, 3 months, 6 months, 1 year, or never
- **Disk space guard** — auto-cleanup when free space drops below threshold; strategies: oldest first, newest first, largest first, smallest first
- **Hourly automated cleanup** via Celery Beat

### GPU Acceleration
Automatically detected at runtime — no configuration needed:

| GPU | Encoder | Detection |
|-----|---------|-----------|
| NVIDIA | `h264_nvenc` | `nvidia-smi` present |
| Apple Metal | `h264_videotoolbox` | macOS + ffmpeg encoder check |
| Intel/AMD | `h264_vaapi` | `/dev/dri/renderD128` exists |
| None | `libx264` (CPU) | Fallback |

GPU is used only when re-encoding is needed (SponsorBlock removal, audio normalization, format conversion, compilation). Simple merges use stream copy — no GPU required.

---

## Installation

### Docker Compose (Recommended)

```bash
git clone https://github.com/wittedinit/UYTDownloader.git
cd UYTDownloader
cp .env.default .env    # Edit settings if needed
docker compose up -d
```

Open **http://your-server-ip:3000** in your browser.

### Unraid (Community Apps)

Search for **UYTDownloader** in the Apps tab and click Install. Then configure:

1. **Configure paths** — map the three volumes to your Unraid shares:

   | Container Path | Suggested Unraid Path | Purpose |
   |---------------|----------------------|---------|
   | `/config` | `/mnt/user/appdata/uytdownloader/config` | Cookies, logs |
   | `/downloads` | `/mnt/user/data/media/youtube` | Completed files |
   | `/work` | `/mnt/user/appdata/uytdownloader/work` | Temp/in-progress |

2. **Configure ports**:

   | Port | Default | Purpose |
   |------|---------|---------|
   | WebUI | `3000` | Frontend (access in browser) |
   | API | `8000` | Backend API |

3. **Set PUID/PGID** — match your Unraid user (typically `PUID=99` `PGID=100` for `nobody:users`)

4. **Set timezone** — e.g., `TZ=Europe/London`

5. **GPU passthrough** (optional) — if you have an NVIDIA GPU passed through to Docker:
   - Add `--runtime=nvidia` to the worker container
   - Set `NVIDIA_VISIBLE_DEVICES=all`
   - Or use the `docker-compose.gpu.yml` override

#### Unraid Environment Variables

| Variable | Default | What to set |
|----------|---------|-------------|
| `PUID` | `1000` | `99` (Unraid nobody user) |
| `PGID` | `1000` | `100` (Unraid users group) |
| `TZ` | `UTC` | Your timezone, e.g., `Europe/London` |
| `UYT_CONCURRENCY_MODE` | `balanced` | Download policy: `safe` (1 worker, 1 fragment, sleeps), `balanced` (3 workers, 3 fragments, light sleeps), `power` (6 workers, 5 fragments, no sleep) |
| `UYT_RETENTION` | `forever` | Auto-delete period: `1_week`, `1_month`, `1_year`, `forever` |
| `UYT_DISK_GUARD_PCT` | `10` | Min free disk % before auto-cleanup starts |
| `UYT_DISK_GUARD_STRATEGY` | `oldest_first` | `oldest_first`, `newest_first`, `largest_first`, `smallest_first` |
| `UYT_SPONSORBLOCK_DEFAULT` | `keep` | `keep`, `mark_chapters`, `remove` |

#### Browser Cookies (Optional)

For age-gated or member-only content, export your YouTube cookies in Netscape format and place them inside your **config volume** at `cookies/youtube.txt`.

**How to export cookies:**

Option 1 — **yt-dlp** (if installed on your host):
```bash
mkdir -p ./config/cookies
yt-dlp --cookies-from-browser chrome --cookies ./config/cookies/youtube.txt --skip-download "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```
Replace `chrome` with `firefox`, `edge`, `safari`, `brave`, or `opera` depending on your browser. You must be logged into YouTube in that browser.

Option 2 — **Browser extension**: Install "Get cookies.txt LOCALLY" (Chrome/Firefox), go to youtube.com while logged in, export cookies, and save the file as `youtube.txt`.

**Where to put the file** depends on where you mapped the `/config` volume:

| Deployment | Cookie file location |
|-----------|---------------------|
| Unraid | `{your config path}/cookies/youtube.txt` (e.g., `/mnt/user/appdata/uytdownloader/config/cookies/youtube.txt`) |
| Docker Compose | `./config/cookies/youtube.txt` (relative to docker-compose.yml) |
| Custom | Wherever you mapped `/config` → put `cookies/youtube.txt` inside it |

The health check at `/health` will show `cookies: present` when configured correctly. Cookies expire — if age-restricted downloads start failing, re-export fresh cookies.

### With NVIDIA GPU

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d
```

---

## Web UI Pages

| Page | URL | Purpose |
|------|-----|---------|
| **Download** | `/` | Probe URLs, select entries, configure quality/format, download or merge. Reset button to clear and start fresh. |
| **Jobs** | `/jobs` | Monitor progress, download completed artifacts, cancel, retry (single or bulk), delete. Bulk retry all failed jobs. |
| **Library** | `/library` | Browse files, download individually or as zip, merge, delete (single or bulk) |
| **Subscriptions** | `/subscriptions` | Manage auto-download subscriptions with filters |
| **Settings** | `/settings` | Download policy mode (safe/balanced/power), disk usage, retention policy, disk guard, system health |
| **Manual** | `/manual` | Comprehensive searchable user guide with quick-start Q&As |

---

## Architecture

```
Browser → Frontend (Next.js :3000)
              ↓
         Backend API (FastAPI :8000) → PostgreSQL (metadata, jobs, subscriptions)
              ↓
         Redis (queue broker)
              ↓
         Worker (Celery) → yt-dlp + deno + ffmpeg
              ↓
         Beat (Celery Beat) → subscription checks, storage cleanup
```

### Docker Services

| Service | Base Image | Purpose |
|---------|-----------|---------|
| `postgres` | postgres:16-alpine | Database |
| `redis` | redis:7-alpine | Queue broker + result backend |
| `backend` | python:3.12-slim + ffmpeg + deno | FastAPI API server + auto-migration |
| `worker` | python:3.12-slim + ffmpeg + deno | Celery worker (downloads, processing) |
| `beat` | (same as worker) | Celery Beat scheduler |
| `frontend` | node:22-alpine | Next.js web UI (standalone build) |

### Job Pipeline

Each download passes through a configurable multi-stage pipeline:

```
revalidate_formats → download_video → download_audio → merge
    → sponsorblock → embed_subtitles → normalize_audio → finalize
```

Stages are added dynamically. Audio-only skips video/merge. Stages like SponsorBlock, subtitles, and normalization are opt-in.

---

## API Reference

30 endpoints across 7 resource groups. Full OpenAPI docs available at `http://your-server:8000/docs`.

<details>
<summary>Expand API reference</summary>

### Probe
```
POST /api/probe                         Submit URL for metadata extraction
GET  /api/probe/{probe_id}              Poll probe result
```

### Jobs
```
POST /api/jobs                          Create download jobs
GET  /api/jobs                          List jobs (filter by status)
GET  /api/jobs/{job_id}                 Get job details (stages, artifacts)
POST /api/jobs/{job_id}/cancel          Cancel a job
POST /api/jobs/{job_id}/retry           Retry a failed job
DELETE /api/jobs/{job_id}               Delete job from history
POST /api/jobs/bulk-delete              Delete multiple jobs
POST /api/jobs/bulk-retry               Retry all failed jobs
```

### Sources & Entries
```
GET  /api/sources                       List probed sources
GET  /api/sources/{source_id}           Get source details
GET  /api/sources/{source_id}/entries   List entries for a source
GET  /api/entries/{entry_id}            Get entry with format snapshot
```

### Subscriptions
```
POST /api/subscriptions                 Create subscription
GET  /api/subscriptions                 List subscriptions
GET  /api/subscriptions/{sub_id}        Get subscription with filters
PATCH /api/subscriptions/{sub_id}       Update subscription
DELETE /api/subscriptions/{sub_id}      Delete subscription
POST /api/subscriptions/{sub_id}/check  Trigger manual check
```

### Compilations
```
POST /api/compilations                  Merge entries into one file
```

### Library
```
GET  /api/library                       List downloaded files
GET  /api/library/download/{filename}   Download a file
DELETE /api/library/{filename}          Delete a file
POST /api/library/merge                 Merge files by filename
POST /api/library/zip                   Create ZIP of selected files
DELETE /api/library/zip/{filename}      Delete ZIP after download
```

### Storage
```
GET  /api/storage/usage                 Disk usage stats
GET  /api/storage/presets               Available retention/strategy options
POST /api/storage/retention             Run retention cleanup
POST /api/storage/disk-guard            Run disk space guard cleanup
```

### Health
```
GET  /health                            System health check
```

</details>

---

## Configuration Reference

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `UYT_PORT` | `8000` | Backend API port |
| `UYT_FRONTEND_PORT` | `3000` | Frontend port |
| `UYT_CONCURRENCY_MODE` | `balanced` | Download policy engine mode — controls pacing, fragment concurrency, and throttle detection. See below. |
| `UYT_SPONSORBLOCK_DEFAULT` | `keep` | Default SponsorBlock action: `keep`, `mark_chapters`, `remove` |
| `UYT_RETENTION` | `forever` | File retention: `1_day`, `1_week`, `1_month`, `3_months`, `6_months`, `1_year`, `forever` |
| `UYT_DISK_GUARD_PCT` | `10` | Auto-cleanup when free disk space below this % |
| `UYT_DISK_GUARD_STRATEGY` | `oldest_first` | Cleanup order: `oldest_first`, `newest_first`, `largest_first`, `smallest_first` |
| `PUID` | `1000` | File owner UID (Unraid: `99`) |
| `PGID` | `1000` | File owner GID (Unraid: `100`) |
| `TZ` | `UTC` | Timezone |
| `NVIDIA_VISIBLE_DEVICES` | `void` | GPU access (`all` to enable) |

### Download Policy Engine

UYTDownloader does not blast YouTube with unconstrained connections. A download policy engine controls how aggressively yt-dlp downloads, reducing the risk of throttling or IP blocking.

| Setting | Safe | Balanced (default) | Power |
|---------|------|----------|-------|
| Fragment concurrency | 1 | 3 | 5 |
| Request sleep | 1.5s | 0.5s | 0s |
| Download sleep | 5–30s | 2–10s | 0s |
| Throttle detection | 100 KB/s | 100 KB/s | 100 KB/s |
| Retries (network/fragment/extractor) | 5/10/5 | 3/5/3 | 3/5/3 |
| Socket timeout | 30s | 20s | 15s |

**How it works:**
- **Request pacing** — sleeps between HTTP requests to mimic normal browsing
- **Download pacing** — sleeps between consecutive video downloads in a queue
- **Fragment concurrency** — controls how many video chunks download in parallel
- **Throttle detection** — if speed drops below 100 KB/s, yt-dlp re-extracts the URL to get a fresh CDN node
- **Automatic retries** — configurable per mode for network errors, fragment failures, and extractor changes

Set `UYT_CONCURRENCY_MODE=safe` if you're on a shared IP or VPN, or if you've been throttled. Use `power` only for fast connections with a few videos.

### Volumes (Persistent Storage)

All three volumes **must be mapped to persistent storage** on your host. Without this, data is lost when containers restart.

| Container Path | Purpose | What to map it to |
|---------------|---------|-------------------|
| `/config` | Cookies, logs, settings | A persistent config directory (e.g., `./config` or `/mnt/user/appdata/uytdownloader/config`) |
| `/downloads` | Completed downloads (your library) | Where you want finished files stored (e.g., `./downloads` or `/mnt/user/data/media/youtube`) |
| `/work` | In-progress downloads, temp files | A scratch directory, can be on fast storage (e.g., `./work` or `/mnt/user/appdata/uytdownloader/work`) |

**Important:** The `/downloads` volume is where all your completed media lives. This is the path your Library page browses. Choose a location with enough space for your download library.

**Cookies** go inside the config volume at `cookies/youtube.txt` (i.e., `{your /config mapping}/cookies/youtube.txt`).

### Quality Presets

**Video:**
| Preset | Hint |
|--------|------|
| `best` | Best Available |
| `2160p` | 4K (Best Quality) |
| `1080p` | Recommended |
| `720p` | Balanced |
| `480p` | Smallest Size |

**Audio:**
| Preset | Hint |
|--------|------|
| `best` | Best Available |
| `audio_320k` | Best Quality |
| `audio_192k` | Recommended |
| `audio_128k` | Good |
| `audio_64k` | Smallest Size |

---

## Development

### Local dev (requires Postgres + Redis running)

```bash
# Backend
cd backend && pip install -e .
uvicorn app.main:app --reload

# Worker
celery -A app.celery_app:celery worker -Q probe,download --loglevel=info

# Beat
celery -A app.celery_app:celery beat --loglevel=info

# Frontend
cd frontend && npm install && npm run dev
```

### Database migrations

```bash
docker compose exec backend bash -c "PYTHONPATH=/app alembic revision --autogenerate -m 'description'"
docker compose exec backend bash -c "PYTHONPATH=/app alembic upgrade head"
```

---

## License

MIT
