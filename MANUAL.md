# UYTDownloader User Manual

> This manual is also available in the web UI at `/manual` with search functionality.

## Quick Start Q&A

**Q: How do I download a YouTube video?**
Go to the Download page, paste the URL, click Probe. Select quality/format options, then click Download.

**Q: How do I download an entire playlist?**
Paste the playlist URL, click Probe. All videos appear as a selectable list. Download individually or click "Download & Merge" for one file.

**Q: Where do my files go?**
All downloads appear in the Library page. Files are stored in the `/downloads` volume on the server.

**Q: How do I remove sponsors?**
Set the SponsorBlock dropdown to "Remove Sponsors" before downloading. Segments are detected via the SponsorBlock community database.

**Q: Can I auto-download from a channel?**
Yes! Probe a channel URL, click Subscribe. Configure filters and the system checks automatically.

**Q: How do I free up disk space?**
Settings page has Retention Policy (auto-delete old files) and Disk Space Guard (auto-cleanup when disk is low).

---

## Download Page

### Probing a URL

1. Paste any YouTube URL (video, playlist, or channel) into the input
2. Click **Probe** — the system extracts all metadata via yt-dlp
3. Results show: thumbnail, title, channel (cyan), date (purple), duration (green) for each entry

Tips:
- Playlist URLs show all videos in the playlist
- Results persist if you navigate away and come back (within same browser session)

### Download Options

| Option | Values | Notes |
|--------|--------|-------|
| **Stream** | Video + Audio, Audio Only, Video Only | Audio Only switches quality to bitrate |
| **Resolution** | Best, 2160p (4K), 1080p, 720p, 480p | For video modes |
| **Audio Quality** | Best, 320/256/192/128/64 kbps | For audio-only mode |
| **Output Format** | Original, MP4/H.264, MP4/H.265, MKV, WebM | Original = no re-encode |
| **Video Bitrate** | Auto, 8000/5000/3000/1500/800 kbps | Only when re-encoding |
| **SponsorBlock** | Keep All, Mark as Chapters, Remove | Uses SponsorBlock API |
| **Embed subtitles** | On/Off | Downloads and embeds available tracks |
| **Normalize audio** | On/Off | EBU R128 loudness normalization |

### Selecting and Reordering

- Check/uncheck entries, or use Select All/Deselect All
- Drag entries by the handle (dots icon) to reorder for merge
- Position numbers (#1, #2, etc.) show the current order

### Actions

- **Download N items** (green) — downloads each as a separate file
- **Download N Items & Merge** (purple) — downloads and merges into one file with chapter markers (2+ items required)
- **Subscribe** (purple, on source card) — creates auto-download subscription (playlists/channels only)

---

## Jobs Page

### Statuses

| Status | Color | Meaning |
|--------|-------|---------|
| Queued | Yellow | Waiting for a worker |
| Running | Blue | Actively downloading (shows % and speed) |
| Completed | Green | Done, file in Library |
| Failed | Red | Error occurred |
| Cancelled | Grey | Manually stopped |

### Job Stages

Each job passes through up to 8 stages:

1. **Revalidate Formats** — re-checks available formats
2. **Download Video** — downloads video stream
3. **Download Audio** — downloads audio stream
4. **Merge** — combines streams via ffmpeg
5. **SponsorBlock** — marks/removes sponsors
6. **Embed Subtitles** — embeds subtitle tracks
7. **Normalize Audio** — loudness normalization
8. **Finalize** — moves to downloads, checksums, archives

Click **Details** to see stage-by-stage progress and artifacts.

### Actions

- **Cancel** — stop a running job
- **Retry** — re-run from point of failure
- **Delete** — remove from history (select + bulk delete supported)
- **Filter** — show only jobs in a specific status

---

## Library Page

### Browsing

Files sorted by most recent. Each shows: type icon, filename, size, date.

### Downloading

Individual: click **Download** on any file.

Bulk: select files → click **Download N** → choose:
- **Download All Individually** — separate browser downloads
- **Zip All & Download** — single ZIP file (stored, no compression). ZIP auto-deleted after download.

### Merging

Select 2+ files → click **Merge N** → enter filename → merged file appears in Library.

### Deleting

Individual or bulk delete with confirmation.

---

## Subscriptions Page

### Creating

Probe a channel/playlist → click **Subscribe** on the source card.

### Filters

| Filter | Description |
|--------|-------------|
| Ignore Shorts | Skip videos < 60 seconds |
| Ignore Live | Skip livestreams |
| Min Duration | Minimum seconds (e.g., 120) |
| Max Duration | Maximum seconds |
| Keyword Include | Title must contain word |
| Keyword Exclude | Title must NOT contain word |

### Managing

- **Check** — trigger immediate check
- **Pause/Resume** — toggle auto-checking
- **Delete** — remove subscription (keeps downloaded files)

---

## Settings Page

### Disk Usage

Visual progress bar + stats: file count, download size, free space %.

### Retention Policy

Auto-deletes files older than the configured period (1 day to 1 year, or forever).
Runs every hour automatically. Use "Preview" for dry-run, "Run Cleanup Now" to execute immediately.

### Disk Space Guard

Auto-deletes files when free disk space drops below threshold.
Strategies: oldest first, newest first, largest first, smallest first.
Runs every hour. Green status = threshold met. Amber = below threshold.

### System Health

Shows: database, redis, ffmpeg, yt-dlp, directory paths. All should be green.

---

## Advanced

### Browser Cookies

For age-gated/member content: export YouTube cookies in Netscape format → place at `config/cookies/youtube.txt`.

### GPU Acceleration

Auto-detected: NVIDIA NVENC → Apple Metal → VA-API → CPU fallback.
Only used for transcoding (not simple merges). Check Settings page for detected GPU.

### Concurrency Modes

- **Safe** — 1 download at a time
- **Balanced** — 3 simultaneous (default)
- **Power** — 6 simultaneous

Set via `UYT_CONCURRENCY_MODE` env var.

### API Access

Full REST API at port 8000. Interactive docs at `http://your-server:8000/docs`.
30 endpoints across probe, jobs, sources, subscriptions, compilations, library, storage, and health.
