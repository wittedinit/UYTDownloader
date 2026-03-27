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

**Q: How do I search inside downloaded videos?**
Go to the Search page. It uses YouTube's subtitles and auto-captions, which are automatically indexed when you download a video. Type any word or phrase to find videos where it was said.

**Q: What are Quick Presets?**
One-click workflow templates on the Download page. Choose "Background Listen", "Archive", "Mobile", or "Podcast" to instantly configure all download options for that use case.

**Q: Is there a browser extension?**
Yes! Load the `/extension` folder as an unpacked extension in Chrome. It adds a "UYT" button to YouTube that sends the current video to your UYTDownloader instance with one click.

---

## Download Page

### Probing a URL

1. Paste any YouTube URL (video, playlist, or channel) into the input
2. Click **Probe** — the system extracts all metadata via yt-dlp
3. Results show: thumbnail, title, channel (cyan), date (purple), duration (green) for each entry

Tips:
- Playlist URLs show all videos in the playlist
- Results persist if you navigate away and come back (within same browser session)
- Click **Reset** to clear results and start fresh with a new URL

### Quick Presets

One-click buttons that configure all download options at once:

| Preset | Stream | Quality | SponsorBlock | Format | Extras |
|--------|--------|---------|-------------|--------|--------|
| **Best Quality** | Video + Audio | Best | Keep All | Original | — |
| **Background Listen** | Audio Only | 192 kbps | Remove | MP3 | Normalize audio |
| **Archive** | Video + Audio | Best | Mark Chapters | Original | Embed subtitles |
| **Mobile** | Video + Audio | 720p | Remove | MP4/H.264 | 3000 kbps bitrate |
| **Podcast** | Audio Only | 128 kbps | Remove | MP3 | Normalize audio |

Select a preset, then fine-tune individual options if needed.

### Download Options

| Option | Values | Notes |
|--------|--------|-------|
| **Stream** | Video + Audio, Audio Only, Video Only | Audio Only switches quality to bitrate |
| **Resolution** | Best, 2160p (4K), 1080p, 720p, 480p | For video modes |
| **Audio Quality** | Best, 320/256/192/128/64 kbps | For audio-only mode |
| **Output Format** | Original, MP4/H.264, MP4/H.265, MKV, WebM | Original = no re-encode |
| **Audio Format** | MP3, M4A/AAC, Opus, FLAC | For audio-only mode |
| **Video Bitrate** | Auto, 8000/5000/3000/1500/800 kbps | Only when re-encoding |
| **SponsorBlock** | Keep All, Mark as Chapters, Remove | Uses SponsorBlock API |
| **Embed subtitles** | On/Off | Downloads and embeds available tracks |
| **Normalize audio** | On/Off | EBU R128 loudness normalization (-16 LUFS) |

### Selecting and Reordering

- Check/uncheck entries, or use Select All/Deselect All
- Drag entries by the handle (dots icon) to reorder for merge
- Position numbers (#1, #2, etc.) show the current order

### Actions

- **Download N items** (green) — downloads each as a separate file
- **Download N Items & Merge** (purple) — downloads and merges into one file with chapter markers (2+ items required)
- **Subscribe** (purple, on source card) — creates auto-download subscription (playlists/channels only)
- **Reset** — clears probe results and returns to empty input state

**Archive dedup:** After clicking Download, you'll see a summary of how many jobs were created vs skipped. Skipped items are videos you've already downloaded with the same settings (same video ID + output configuration). This prevents re-downloading content you already have.

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
8. **Finalize** — moves to downloads, checksums, archives, indexes transcript

Click **Details** to see stage-by-stage progress and artifacts.

### Download Artifacts

Completed jobs show download links for their output files. You can download the result directly from the Jobs page without going to the Library.

If a file has been deleted from the Library, the job will show "Source File Deleted" — the job history is preserved even after file cleanup.

### Actions

- **Cancel** — stop a running job
- **Retry** — re-run a failed job (resets status and restarts from the failed stage)
- **Bulk Retry** — select multiple failed jobs and retry them all at once
- **Delete** — remove from history (select + bulk delete supported)
- **Filter** — show only jobs in a specific status (All, Queued, Running, Completed, Failed)

---

## Library Page

### Browsing

The Library shows all completed downloads with search, sort, and filter controls:

**Search bar** — type to filter files by name (case-insensitive, debounced). Clear with the X button.

**Type filter** — show All files, Video only, or Audio only.

**Sort options:**
- Newest First (default)
- Oldest First
- Name A-Z / Name Z-A
- Largest First / Smallest First

Each file shows: type icon (video/audio), filename, size, date modified.

### Downloading

Individual: click **Download** on any file.

Bulk: select files → click **Download N** → choose:
- **Download All Individually** — separate browser downloads
- **Zip All & Download** — single ZIP file (stored, no compression). ZIP auto-deleted after download.

### Merging

Select 2+ files → click **Merge N** → enter filename → merged file appears in Library with chapter markers at each file boundary.

### Deleting

Individual or bulk delete with confirmation. Permanently removes files from the server.

---

## Search Page

### How Transcript Search Works

UYTDownloader automatically indexes the transcript of every video you download. When the finalize stage completes, the system:

1. Fetches English subtitles or auto-generated captions from YouTube via yt-dlp
2. Parses the subtitle text (strips timestamps, HTML tags, deduplicates repeated lines)
3. Stores the plain text in PostgreSQL with a GIN full-text search index
4. Weights the search: title matches rank highest, then channel name, then transcript content

### Searching

1. Go to the **Search** page from the sidebar
2. Type any word or phrase into the search bar
3. Results are ranked by relevance
4. Each result shows: video title, channel name, language, and a text snippet with matching words highlighted
5. Click **YouTube** to open the original video on YouTube

The stats line shows how many videos are indexed and estimated hours of searchable content.

### What Gets Indexed

- **English subtitles** are preferred (manual subs first, then auto-captions)
- YouTube's auto-generated captions cover approximately 95% of English-language videos
- Videos without any subtitles or captions are not indexed
- Short clips, non-English content, and very new uploads may lack captions
- Transcripts are indexed once at download time — re-downloading updates the index

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

Multiple filters can be combined. All enabled filters must pass for a video to be auto-downloaded.

### Managing

- **Check** — trigger immediate check
- **Pause/Resume** — toggle auto-checking
- **Delete** — remove subscription (keeps downloaded files)

---

## Settings Page

### Download Policy Mode

Controls how aggressively yt-dlp downloads. Can be changed from the Settings UI or via `UYT_CONCURRENCY_MODE` environment variable.

| Mode | Fragments | Request Sleep | Download Sleep | Best For |
|------|-----------|--------------|----------------|----------|
| **Safe** | 1 | 1.5s | 5–30s | Shared IPs, VPNs, after throttling |
| **Balanced** | 3 | 0.5s | 2–10s | Most users (default) |
| **Power** | 5 | None | None | Fast connections, few videos |

All modes include throttle detection at 100 KB/s — if speed drops below this, yt-dlp re-extracts the URL to get a fresh CDN node.

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

Shows: database, redis, ffmpeg version, yt-dlp version, GPU detection, download policy mode, cookie status, directory paths. All should be green.

---

## Advanced

### Browser Cookies

For age-gated/member content, export YouTube cookies and place them in your config volume.

**Method 1 — yt-dlp (if installed on host):**
```bash
mkdir -p ./config/cookies
yt-dlp --cookies-from-browser chrome --cookies ./config/cookies/youtube.txt --skip-download "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```
Replace `chrome` with `firefox`, `edge`, `safari`, `brave`, or `opera`.

**Method 2 — Browser extension:**
Install "Get cookies.txt LOCALLY", go to youtube.com while logged in, export, save as `cookies/youtube.txt` inside your `/config` volume.

**Important:** Cookies expire. If age-restricted downloads start failing, re-export fresh cookies.

The health check at `/health` shows `cookies: present` when configured correctly.

### Browser Extension

A Chrome extension is included in the `/extension` directory.

**Installation:**
1. Open `chrome://extensions` in Chrome
2. Enable **Developer mode** (toggle in top-right)
3. Click **Load unpacked** → select the `extension` folder from the repo

**Features:**
- **Popup** — click the extension icon to configure your server URL and send the current YouTube page
- **YouTube button** — a purple "UYT" button is injected into YouTube's action bar on video, playlist, and channel pages
- **One-click send** — probes the URL and opens your UYTDownloader web UI with the URL pre-filled
- **Visual feedback** — button shows loading (grey), success (green), or error (red) states

### GPU Acceleration

Auto-detected: NVIDIA NVENC → Apple Metal → VA-API → CPU fallback.
Only used for transcoding (not simple merges). Check Settings page for detected GPU.

For NVIDIA on Unraid: install NVIDIA Driver plugin, add `NVIDIA_VISIBLE_DEVICES=all` to container settings.

### Download Policy Engine

Controls pacing, fragment concurrency, and throttle detection. See Settings → Download Policy Mode.

**What it does behind the scenes:**
- **Request pacing** — sleeps between HTTP requests to mimic normal browsing
- **Download pacing** — sleeps between consecutive video downloads in a queue
- **Fragment concurrency** — how many video chunks download in parallel
- **Throttle detection** — re-extracts URL if speed drops below 100 KB/s
- **Automatic retries** — configurable per mode for network, fragment, and extractor errors

**Tip:** If consistently slow or failing, switch to Safe mode. If throttled, wait 15–30 minutes and use browser cookies.

### API Access

Full REST API at port 8000. Interactive docs at `http://your-server:8000/docs`.
31 endpoints across probe, jobs, sources, subscriptions, compilations, library, storage, search, and health.

### Mobile Responsive

The entire web UI is responsive and works on mobile, tablet, and desktop screens. All pages adapt layout, cards, and controls for smaller viewports. Touch-friendly selection and download actions work on mobile devices.
