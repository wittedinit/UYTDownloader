"use client";

import { useState, useMemo } from "react";

// ── Manual content structure ──────────────────────────────────────────

interface FAQ {
  q: string;
  a: string;
}

interface Section {
  id: string;
  title: string;
  icon: string;
  content: SubSection[];
}

interface SubSection {
  id: string;
  title: string;
  body: string;
}

const FAQS: FAQ[] = [
  {
    q: "How do I download a YouTube video?",
    a: "Go to the Download page, paste the YouTube URL into the input box, and click Probe. Once the video details appear, select your preferred quality and format options, then click the green Download button.",
  },
  {
    q: "How do I download an entire playlist?",
    a: "Paste the playlist URL on the Download page and click Probe. All videos in the playlist will appear as a selectable list. You can download them individually or click 'Download & Merge' to combine them into one file with chapters.",
  },
  {
    q: "Where do my downloaded files go?",
    a: "All completed downloads appear in the Library page. From there you can download them to your computer, merge multiple files, or delete them. The files are stored in the /downloads volume on the server.",
  },
  {
    q: "How do I remove sponsor segments?",
    a: "On the Download page, set the SponsorBlock dropdown to 'Remove Sponsors'. This will automatically detect and cut out sponsor segments, intros, outros, and subscription reminders using the SponsorBlock community database.",
  },
  {
    q: "Can I subscribe to a channel for automatic downloads?",
    a: "Yes! Probe a channel or playlist URL, then click the purple 'Subscribe' button on the source card. You can configure filters (ignore shorts, min duration, keywords) and the system will automatically check for and download new content.",
  },
  {
    q: "How do I free up disk space?",
    a: "Go to Settings. You can set a Retention Policy to auto-delete old files, or use the Disk Space Guard to automatically clean up when free space gets low. You can also manually delete files from the Library page.",
  },
  {
    q: "How do I search inside downloaded videos?",
    a: "Go to the Search page. UYTDownloader automatically indexes YouTube subtitles and auto-captions when you download a video. You can search by keyword and results are ranked by relevance, with matching context snippets highlighted.",
  },
  {
    q: "What are Quick Presets?",
    a: "Quick Presets are one-click workflow templates on the Download page. Choose from Best Quality, Background Listen, Archive, Mobile, or Podcast — each pre-fills format, quality, SponsorBlock, subtitle, normalization, and output format settings. You can fine-tune any option after selecting a preset.",
  },
  {
    q: "Is there a browser extension?",
    a: "Yes! A Chrome extension is included in the /extension directory. Load it as an unpacked extension in chrome://extensions. It adds a 'UYT' button to YouTube's action bar so you can send videos to your server with one click.",
  },
];

const SECTIONS: Section[] = [
  {
    id: "download",
    title: "Download",
    icon: "M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4",
    content: [
      {
        id: "download-probe",
        title: "Probing a URL",
        body: `**What it does:** Extracts metadata from a YouTube URL without downloading anything.

**How to use:**
1. Paste any YouTube URL into the input box — this can be a single video, a playlist, or a channel URL
2. Click the blue **Probe** button
3. Wait for the spinner — the system contacts YouTube via yt-dlp to extract all metadata
4. Once complete, you'll see the source info (title, channel, item count) and a list of all discovered videos

**What you see for each video:**
- Thumbnail image
- Video title
- Channel name (cyan pill)
- Published date (purple pill, formatted as YYYY-MM-DD)
- Duration (green pill)
- Checkbox to select/deselect

**Tips:**
- Probing a playlist shows ALL videos in the playlist, not just the first page
- Probing a channel shows recent uploads
- The probe results persist if you navigate to other pages and come back (within the same browser session)`,
      },
      {
        id: "download-options",
        title: "Download Options",
        body: `**Stream type:**
- **Video + Audio** — downloads both video and audio streams, merges them into one file (MP4)
- **Audio Only** — downloads only the audio track. Quality dropdown switches to audio bitrate options
- **Video Only** — downloads only the video stream with no audio

**Resolution (for video):**
- **Best Available** — highest quality YouTube offers for this video
- **2160p (4K)** — best quality, largest files
- **1080p** — recommended, good balance of quality and size
- **720p** — balanced, smaller files
- **480p** — smallest files

**Audio Quality (for audio-only):**
- **Best Available** — highest bitrate available
- **320 kbps** — best quality
- **192 kbps** — recommended
- **128 kbps** — good for speech/podcasts
- **64 kbps** — smallest size

**Output Format (optional re-encoding):**
- **Original (No Re-encode)** — keeps the format YouTube provides (fastest, no quality loss)
- **MP4 / H.264** — most compatible format (recommended if re-encoding)
- **MP4 / H.265** — smaller file size at same quality
- **MKV / H.264** — for media servers
- **WebM / VP9** — open format

**Video Bitrate** (only when re-encoding):
- **Auto** — matches source bitrate
- **8,000 kbps** — best quality for 4K
- **5,000 kbps** — recommended for 1080p
- **3,000 kbps** — good for 720p
- **1,500 kbps / 800 kbps** — smaller files

**SponsorBlock:**
- **Keep All** — no sponsor removal
- **Mark as Chapters** — sponsor segments become chapter markers (you can skip them manually)
- **Remove Sponsors** — automatically cuts out sponsor segments, intros, outros, self-promo

**Post-processing:**
- **Embed subtitles** — downloads available subtitle tracks and embeds them in the file
- **Normalize audio** — adjusts loudness to a consistent level (EBU R128 standard, -16 LUFS)`,
      },
      {
        id: "download-presets",
        title: "Quick Presets",
        body: `One-click workflow templates that pre-fill all download options. Select a preset, then fine-tune any individual setting before downloading.

**Best Quality:**
- Video + Audio, Best Available resolution, Original format (no re-encode), SponsorBlock: Mark as Chapters, Embed subtitles on, Normalize audio off

**Background Listen:**
- Audio Only, 192 kbps, Original format, SponsorBlock: Remove Sponsors, Subtitles off, Normalize audio on

**Archive:**
- Video + Audio, Best Available resolution, MKV / H.264, SponsorBlock: Keep All, Embed subtitles on, Normalize audio off

**Mobile:**
- Video + Audio, 720p, MP4 / H.264, SponsorBlock: Remove Sponsors, Subtitles off, Normalize audio on

**Podcast:**
- Audio Only, 128 kbps, Original format, SponsorBlock: Remove Sponsors, Subtitles off, Normalize audio on

**Tip:** After selecting a preset, all options are unlocked for fine-tuning. The preset just gives you a starting point.`,
      },
      {
        id: "download-selecting",
        title: "Selecting and Reordering",
        body: `**Selecting entries:**
- Click the checkbox next to any video to select/deselect it
- Use **Select All** / **Deselect All** to toggle all at once
- The selected count is shown in the top-right of the entry list

**Reordering (for merge):**
- Each entry has a drag handle (dots icon) on the left
- Drag entries up or down to change their order
- The position number (#1, #2, etc.) updates as you reorder
- When you click "Download & Merge", files are merged in the order shown
- A purple "Drag to reorder for merge" hint appears when 2+ items are selected`,
      },
      {
        id: "download-actions",
        title: "Download and Merge",
        body: `**Download button (green):**
- Downloads each selected video as a separate file
- Files appear in the Library once complete
- Each video becomes its own job in the Jobs page

**Download & Merge button (purple):**
- Only appears when 2 or more items are selected
- Downloads all selected videos, then merges them into a single file
- Chapter markers are added at each video boundary
- The merged file title defaults to the playlist/channel name
- Uses the merge order from the entry list (drag to reorder)

**Reset button:**
- Clears probe results and starts fresh — useful when you want to probe a different URL or clear stale metadata

**Subscribe button (purple, on source card):**
- Only appears for playlists and channels (not single videos)
- Creates a subscription that auto-checks for new content
- Uses your current format/quality/SponsorBlock settings

**Archive dedup and feedback:**
- After clicking Download, a summary shows how many jobs were created vs skipped
- Skipped items are videos you've already downloaded with the same settings (same video ID + output configuration)
- This prevents accidentally re-downloading content you already have
- If all selected items are already archived, no jobs are created and you'll see an explanation`,
      },
    ],
  },
  {
    id: "jobs",
    title: "Jobs",
    icon: "M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4",
    content: [
      {
        id: "jobs-status",
        title: "Job Statuses",
        body: `Every download goes through a series of stages. The Jobs page shows the current status of each:

- **Queued** (yellow) — waiting to be picked up by a worker
- **Running** (blue) — actively downloading or processing, shows progress % and speed
- **Completed** (green) — finished successfully, file available in Library
- **Failed** (red) — something went wrong, error message shown
- **Cancelled** (grey) — manually cancelled by you

**Progress tracking:**
During download, you'll see a live progress bar with percentage and download speed (e.g., "45% · 12.3 MB/s"). This updates every few seconds.`,
      },
      {
        id: "jobs-stages",
        title: "Job Stages (Detail View)",
        body: `Click **Details** on any job to see its stage-by-stage breakdown:

1. **Revalidate Formats** — re-checks YouTube for available formats (ensures fresh data)
2. **Download Video** — downloads the video stream
3. **Download Audio** — downloads the audio stream
4. **Merge** — combines video + audio into one file using ffmpeg
5. **SponsorBlock** — marks or removes sponsor segments (if enabled)
6. **Embed Subtitles** — downloads and embeds subtitle tracks (if enabled)
7. **Normalize Audio** — adjusts loudness to consistent level (if enabled)
8. **Finalize** — moves file to downloads folder, calculates checksum, creates archive record

Not all stages run every time. Audio-only downloads skip video/merge. Stages like SponsorBlock, subtitles, and normalization are opt-in.

The detail view also shows **Artifacts** — the actual files produced (video stream, audio stream, merged file) with sizes and download links.`,
      },
      {
        id: "jobs-actions",
        title: "Managing Jobs",
        body: `**Filter buttons:**
Use the filter pills (All, Queued, Running, Completed, Failed) to show only jobs in that state.

**Cancel:**
Stop a running or queued job. The worker will terminate the download.

**Retry:**
Re-run a failed job from the point of failure. Only available for failed jobs.

**Bulk Retry:**
Select multiple failed jobs using checkboxes and click "Retry N jobs" to re-queue them all at once.

**Download Artifacts:**
Completed jobs show download links for their output files directly in the job card. Click to download the finished file without navigating to the Library.

**Source File Tracking:**
If a completed job's output file was later deleted from the Library, the job card indicates the file is no longer available on disk.

**Delete:**
Remove a job from history. Use the checkbox + "Delete N jobs" for bulk deletion, or the Delete button on individual jobs. Running jobs must be cancelled before deletion.

**Select All:**
Check all visible jobs for bulk operations.`,
      },
    ],
  },
  {
    id: "library",
    title: "Library",
    icon: "M5 19a2 2 0 01-2-2V7a2 2 0 012-2h4l2 2h4a2 2 0 012 2v1M5 19h14a2 2 0 002-2v-5a2 2 0 00-2-2H9a2 2 0 00-2 2v5a2 2 0 01-2 2z",
    content: [
      {
        id: "library-browse",
        title: "Browsing Files",
        body: `The Library shows all completed downloads in the server's downloads folder.

**Each file shows:**
- File type icon (video camera for video files, music note for audio)
- Filename
- File size
- Date modified

**Search bar:**
Type to filter files by name. Search is debounced and case-insensitive — results update as you type.

**Type filter:**
Filter files by type using the pills: **All**, **Video**, or **Audio**.

**Sort options:**
- **Newest** — most recently modified first (default)
- **Oldest** — oldest files first
- **Name A-Z** — alphabetical
- **Name Z-A** — reverse alphabetical
- **Largest** — biggest files first
- **Smallest** — smallest files first`,
      },
      {
        id: "library-download",
        title: "Downloading Files",
        body: `**Individual download:**
Click the **Download** button on any file to download it directly to your browser's download folder.

**Bulk download:**
1. Select files using checkboxes (or click **Select All**)
2. Click the green **Download N** button
3. A dialog appears with two options:
   - **Download All Individually** — triggers a separate browser download for each file
   - **Zip All & Download** — bundles all selected files into a single ZIP file (stored mode, no compression for speed) and downloads it. The ZIP is automatically deleted from the server after download.
4. **Cancel** — close the dialog without downloading`,
      },
      {
        id: "library-merge",
        title: "Merging Files",
        body: `You can merge downloaded files directly from the Library:

1. Select 2 or more files using checkboxes
2. Click the purple **Merge N** button
3. Enter a name for the merged file
4. The system automatically detects whether to create a video or audio compilation
5. Chapter markers are added at each file boundary
6. The merged file appears as a new entry in the Library

**Note:** Merging requires re-encoding if the source files have different codecs or resolutions. This can take time for large files.`,
      },
      {
        id: "library-delete",
        title: "Deleting Files",
        body: `**Individual delete:**
Click the red **Delete** button on any file. A confirmation prompt appears.

**Bulk delete:**
1. Select files using checkboxes
2. Click the red **Delete N files** button
3. Confirm the deletion

Deleted files are permanently removed from the server's downloads folder.`,
      },
    ],
  },
  {
    id: "search",
    title: "Search",
    icon: "M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z",
    content: [
      {
        id: "search-how",
        title: "How Transcript Search Works",
        body: `UYTDownloader automatically indexes YouTube subtitles and auto-captions when you download a video.

**Indexing pipeline:**
- When a download completes, the system fetches the video's subtitle tracks from YouTube
- English subtitles are preferred; if unavailable, it falls back to auto-generated captions
- The transcript text is stored in PostgreSQL with full-text search indexing
- Search ranking is weighted: title matches rank highest, then channel name, then transcript content

**Coverage:**
- Approximately 95% of English-language YouTube content has subtitles or auto-captions available
- Videos without any captions are not indexed and won't appear in search results`,
      },
      {
        id: "search-using",
        title: "Searching",
        body: `**How to search:**
1. Go to the Search page
2. Type your query into the search box
3. Results are ranked by relevance using PostgreSQL full-text search

**Results display:**
- Each result shows the video title, channel name, and a context snippet
- Matching terms are highlighted in the snippet so you can see exactly where your query appears
- Click a result to navigate to the file in the Library`,
      },
      {
        id: "search-indexed",
        title: "What Gets Indexed",
        body: `**Subtitle sources (in priority order):**
1. **English subtitles** — human-written captions uploaded by the creator
2. **Auto-generated captions** — YouTube's automatic speech recognition (ASR)

**Coverage notes:**
- ~95% of English-language YouTube content has at least auto-captions
- Non-English content may have lower coverage depending on language support
- Videos without any subtitle track (captions disabled, no ASR available) are not indexed
- Live streams may not have captions available at download time

**What is stored:**
- Full transcript text (all subtitle cues concatenated)
- Video title and channel name (also searchable)
- Timestamps are not currently stored — search finds the video, not the exact moment`,
      },
    ],
  },
  {
    id: "archive",
    title: "Archive",
    icon: "M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4",
    content: [
      {
        id: "archive-overview",
        title: "What is the Archive?",
        body: `The Archive is a **metadata-only** reference table that prevents duplicate downloads. **No actual video or audio files are stored in the archive.**

When you download a video, UYTDownloader records:
- The YouTube video ID
- The output settings used (format, quality, SponsorBlock action)
- The date it was first downloaded

Next time you try to download the same video with the same settings, it will be automatically skipped to save bandwidth and storage.`,
      },
      {
        id: "archive-browse",
        title: "Browsing the Archive",
        body: `Go to the **Archive** page from the sidebar to see all tracked downloads.

Each record shows:
- Video thumbnail and title (when available)
- Uploader name
- Date first downloaded
- YouTube video ID

Use the **search bar** to find records by title or video ID.`,
      },
      {
        id: "archive-remove",
        title: "Removing Archive Records",
        body: `To allow re-downloading a video that was previously downloaded:

1. Find the record in the Archive page
2. Click **Remove** on the individual record, or
3. Select multiple records and click **Remove from Archive**

This deletes the metadata reference only — it does not affect any downloaded files in your Library.

**Alternative:** When downloading a playlist with archived entries, the confirmation screen shows a **"Re-download Skipped"** button that bypasses dedup for all skipped entries without visiting the Archive page.`,
      },
    ],
  },
  {
    id: "subscriptions",
    title: "Subscriptions",
    icon: "M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9",
    content: [
      {
        id: "subs-create",
        title: "Creating a Subscription",
        body: `**From the Download page:**
1. Probe a channel or playlist URL
2. Click the purple **Subscribe** button on the source card
3. The subscription is created with your current format/quality/SponsorBlock settings
4. An "ignore shorts" filter is added by default

**What happens next:**
The system automatically checks the channel/playlist for new content at regular intervals (default: every 60 minutes). New videos matching your filters are automatically queued for download.`,
      },
      {
        id: "subs-filters",
        title: "Subscription Filters",
        body: `Filters control which new videos are auto-downloaded:

- **Ignore Shorts** — skip videos shorter than 60 seconds (YouTube Shorts)
- **Ignore Live** — skip livestreams and "was live" content
- **Min Duration** — only download videos longer than X seconds (e.g., 120 = skip under 2 minutes)
- **Max Duration** — only download videos shorter than X seconds
- **Keyword Include** — only download if the title contains this word
- **Keyword Exclude** — skip if the title contains this word

Multiple filters can be combined. All enabled filters must pass for a video to be auto-downloaded.`,
      },
      {
        id: "subs-manage",
        title: "Managing Subscriptions",
        body: `**Each subscription card shows:**
- Channel/playlist name and type
- Active/Paused status
- Format, quality, and SponsorBlock settings
- Check interval, last checked, next check times
- Number of tracked entries

**Actions:**
- **Check** — manually trigger a check right now (doesn't wait for the next scheduled check)
- **Pause** / **Resume** — temporarily stop/start automatic checking
- **Delete** — remove the subscription entirely (doesn't delete already-downloaded files)`,
      },
    ],
  },
  {
    id: "settings",
    title: "Settings",
    icon: "M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z M15 12a3 3 0 11-6 0 3 3 0 016 0z",
    content: [
      {
        id: "settings-policy",
        title: "Download Policy Mode",
        body: `The download policy mode can now be changed directly from the Settings UI — no need to set the \`UYT_CONCURRENCY_MODE\` environment variable manually.

**Safe:**
- Most conservative. 1 concurrent fragment, long sleeps between requests and downloads. Best for shared IPs, VPNs, or recovering from throttling.

**Balanced (default):**
- Good speed without attracting attention. 3 concurrent fragments, moderate request pacing. Recommended for most users.

**Power:**
- Maximum speed. 5 concurrent fragments, no sleep between requests. Higher risk of temporary throttling — use for quick bursts only.

Changing the mode takes effect immediately for new downloads. Running downloads keep their original policy.`,
      },
      {
        id: "settings-disk",
        title: "Disk Usage",
        body: `Shows your server's storage status:

- **Progress bar** — visual indicator of used vs free space (turns amber above 70%, red above 90%)
- **Stats cards:**
  - **Files** — number of files in the downloads folder
  - **Downloads** — total size of all downloaded files
  - **Free Space** — percentage of disk space remaining`,
      },
      {
        id: "settings-retention",
        title: "Retention Policy",
        body: `**What it does:** Automatically deletes downloaded files older than the configured period.

**Options:**
- **Forever** — never auto-delete files (default)
- **1 Day / 1 Week / 1 Month / 3 Months / 6 Months / 1 Year** — files older than this are deleted

**How it works:**
- Runs automatically every hour via a background scheduler
- Only deletes files in the downloads folder
- Does not delete job history or database records

**Buttons:**
- **Preview What Would Be Deleted** — shows which files would be removed without actually deleting them (dry run)
- **Run Cleanup Now** — immediately deletes matching files (with confirmation dialog)`,
      },
      {
        id: "settings-guard",
        title: "Disk Space Guard",
        body: `**What it does:** Monitors free disk space and automatically deletes files when it drops below a threshold.

**Settings:**
- **Minimum free space (%)** — the threshold. Default is 10%. If free space falls below this, cleanup begins.
- **Cleanup strategy** — which files to delete first:
  - **Oldest first** — deletes the oldest files first (default, good for keeping recent content)
  - **Newest first** — deletes the most recent files first
  - **Largest first** — deletes the biggest files first (frees space fastest)
  - **Smallest first** — deletes the smallest files first (removes the most files)

**How it works:**
- Checked automatically every hour
- If free space is ABOVE the threshold, nothing happens
- If free space is BELOW the threshold, files are deleted using the chosen strategy until space is recovered
- The current status is shown: green if threshold is met, amber if below

**Buttons:**
- **Preview What Would Be Deleted** — shows what would happen without actually deleting
- **Run Guard Now** — immediately runs the check (with confirmation dialog explaining the behavior)`,
      },
      {
        id: "settings-health",
        title: "System Health",
        body: `Shows the status of all backend components:

- **database** — PostgreSQL connection status
- **redis** — Redis queue broker status
- **ffmpeg** — ffmpeg version installed in the worker container
- **yt_dlp** — yt-dlp version (the YouTube extraction engine)
- **gpu** — detected GPU acceleration (NVIDIA, Metal, VA-API, or CPU fallback)
- **download_policy** — active download mode, fragment concurrency, request sleep, and throttle detection threshold
- **cookies** — whether browser cookies are configured (needed for age-gated content)
- **config_dir / output_dir / work_dir** — configured directory paths

All values should show green. If any show red, the corresponding service may need to be restarted.`,
      },
    ],
  },
  {
    id: "advanced",
    title: "Advanced",
    icon: "M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4",
    content: [
      {
        id: "advanced-cookies",
        title: "Browser Cookies",
        body: `**When needed:** For downloading age-gated, private, or member-only content.

**How to set up:**
1. Install a browser extension that exports cookies in Netscape/HTTP format (e.g., "Get cookies.txt LOCALLY")
2. Log into YouTube in your browser
3. Export cookies for youtube.com
4. Place the exported file inside your config volume at: \`cookies/youtube.txt\` (the full path depends on where you mapped the /config volume — e.g., \`./config/cookies/youtube.txt\` for Docker Compose)
5. Restart the backend and worker containers

**Alternative: yt-dlp command method:**
If you have yt-dlp installed locally, you can export cookies directly from your browser:
\`yt-dlp --cookies-from-browser chrome --cookies ./config/cookies/youtube.txt --skip-download "https://www.youtube.com"\`
This reads Chrome's cookie store and writes a Netscape-format cookie file in one step.

**Cookie expiry:**
YouTube cookies expire periodically (typically every few months). If age-gated or member-only downloads start failing, re-export your cookies. The health check will still show "cookies: present" even if the cookies have expired — it only checks that the file exists.

The health check will show "cookies: present" when configured correctly.`,
      },
      {
        id: "advanced-gpu",
        title: "GPU Acceleration",
        body: `**What it does:** Uses your GPU for video re-encoding operations, making them significantly faster.

**When it's used:** Only during transcoding operations — SponsorBlock segment removal, audio normalization, format conversion, and compilation merging. Simple video+audio merges use stream copy (no GPU needed).

**Detection (automatic):**
- **NVIDIA GPU** — detected via nvidia-smi. Uses H.264 NVENC encoder.
- **Apple Metal** — detected on macOS via ffmpeg VideoToolbox support.
- **Intel/AMD VA-API** — detected via /dev/dri/renderD128 on Linux.
- **No GPU** — falls back to CPU (libx264). Works fine, just slower for large files.

**Unraid NVIDIA setup:**
1. Install the NVIDIA Driver plugin from Community Apps
2. In your container settings, add: \`NVIDIA_VISIBLE_DEVICES=all\`
3. Or use \`docker-compose.gpu.yml\` override

The Settings page shows which GPU (if any) was detected.`,
      },
      {
        id: "advanced-concurrency",
        title: "Download Policy Engine",
        body: `UYTDownloader includes a download policy engine that controls how aggressively yt-dlp downloads. This is critical for avoiding YouTube throttling and IP blocking.

**Three profiles** — set via \`UYT_CONCURRENCY_MODE\` environment variable:

**Safe:**
- 1 concurrent fragment download
- 1.5 second sleep between HTTP requests
- 5–30 second sleep between video downloads
- Maximum retry counts (5 retries, 10 fragment retries)
- Best for: shared IPs, VPNs, or if you've been throttled

**Balanced (default):**
- 3 concurrent fragment downloads
- 0.5 second sleep between HTTP requests
- 2–10 second sleep between video downloads
- Standard retry counts
- Best for: most users, good speed without attracting attention

**Power:**
- 5 concurrent fragment downloads
- No request or download sleep
- Standard retry counts
- Best for: fast connections, downloading a few videos quickly
- Warning: higher risk of temporary throttling

**What the engine does behind the scenes:**
- **Throttle detection** — if download speed drops below 100 KB/s, yt-dlp automatically re-extracts the URL to get a fresh CDN node (YouTube sometimes routes to slow servers as a soft throttle)
- **Request pacing** — sleeps between HTTP requests to mimic normal browsing patterns
- **Download pacing** — sleeps between consecutive video downloads in a queue
- **Fragment concurrency** — controls how many video chunks download in parallel (YouTube serves videos as many small fragments)
- **Automatic retries** — with configurable counts for network errors, fragment failures, and extractor changes

**Health check:** Visit Settings → System Health to see the active download policy including mode, fragment concurrency, request sleep, and throttle detection threshold.

**Tip:** If downloads are consistently slow or failing, try switching to Safe mode. If you've been throttled, wait 15–30 minutes and use browser cookies for authentication.`,
      },
      {
        id: "advanced-api",
        title: "API Access",
        body: `UYTDownloader has a full REST API at port 8000. You can automate downloads, manage subscriptions, and query job status programmatically.

**Interactive API docs:** Visit \`http://your-server:8000/docs\` for the auto-generated Swagger/OpenAPI interface.

**Key endpoints:**
- \`POST /api/probe\` — submit URL for metadata extraction
- \`POST /api/jobs\` — create download jobs
- \`GET /api/jobs\` — list all jobs
- \`POST /api/subscriptions\` — create subscription
- \`GET /api/library\` — list downloaded files
- \`GET /health\` — system health check

See the README for the full API reference with 30 endpoints.`,
      },
      {
        id: "advanced-extension",
        title: "Browser Extension",
        body: `A Chrome extension is included in the \`/extension\` directory for sending YouTube videos to UYTDownloader with one click.

**Installation:**
1. Open \`chrome://extensions\` in Chrome
2. Enable **Developer mode** (toggle in the top-right corner)
3. Click **Load unpacked** and select the \`/extension\` directory from the project
4. The UYT extension icon appears in your toolbar

**Popup (click the extension icon):**
- Configure your UYTDownloader server URL (e.g., \`http://192.168.1.100:3000\`)
- Click **Send** to send the current YouTube page URL to your server for download

**Content script (on YouTube pages):**
- A **UYT** button is added to YouTube's video action bar (next to Like, Share, etc.)
- Click it to send the current video URL to your server with one click
- The web UI opens automatically with the URL pre-filled, ready for probing

**Tip:** Make sure your server URL is accessible from the browser — if you're running UYTDownloader on a different machine, use the LAN IP, not localhost.`,
      },
    ],
  },
];

// ── Component ─────────────────────────────────────────────────────────

export default function ManualPage() {
  const [search, setSearch] = useState("");
  const [activeSection, setActiveSection] = useState<string | null>(null);

  // Filter sections and subsections by search term
  const filtered = useMemo(() => {
    if (!search.trim()) return SECTIONS;
    const q = search.toLowerCase();
    return SECTIONS.map((section) => ({
      ...section,
      content: section.content.filter(
        (sub) =>
          sub.title.toLowerCase().includes(q) ||
          sub.body.toLowerCase().includes(q) ||
          section.title.toLowerCase().includes(q)
      ),
    })).filter((s) => s.content.length > 0);
  }, [search]);

  const filteredFaqs = useMemo(() => {
    if (!search.trim()) return FAQS;
    const q = search.toLowerCase();
    return FAQS.filter((f) => f.q.toLowerCase().includes(q) || f.a.toLowerCase().includes(q));
  }, [search]);

  const scrollTo = (id: string) => {
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  // Simple markdown-like rendering
  const renderBody = (text: string) => {
    return text.split("\n").map((line, i) => {
      const trimmed = line.trim();
      if (!trimmed) return <br key={i} />;

      // Bold
      const parts = trimmed.split(/\*\*(.*?)\*\*/g);
      const rendered = parts.map((part, j) =>
        j % 2 === 1 ? <strong key={j} className="text-[var(--foreground)] font-semibold">{part}</strong> : part
      );

      // Backtick code
      const withCode = rendered.flatMap((part, j) => {
        if (typeof part !== "string") return [part];
        return part.split(/`(.*?)`/g).map((seg, k) =>
          k % 2 === 1 ? <code key={`${j}-${k}`} className="px-1.5 py-0.5 bg-[var(--background)] rounded text-xs font-mono text-indigo-400">{seg}</code> : seg
        );
      });

      // List items
      if (trimmed.startsWith("- ")) {
        return <li key={i} className="ml-4 text-sm text-[var(--muted)] leading-relaxed">{withCode.map((p, pi) => typeof p === "string" ? p.replace(/^- /, "") : p)}</li>;
      }
      if (/^\d+\.\s/.test(trimmed)) {
        return <li key={i} className="ml-4 text-sm text-[var(--muted)] leading-relaxed list-decimal">{withCode.map((p, pi) => typeof p === "string" ? p.replace(/^\d+\.\s/, "") : p)}</li>;
      }

      return <p key={i} className="text-sm text-[var(--muted)] leading-relaxed">{withCode}</p>;
    });
  };

  return (
    <div className="p-6 lg:p-8 max-w-screen-xl mx-auto w-full">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-2xl font-bold mb-1">Manual</h1>
        <p className="text-sm text-[var(--muted)]">Complete guide to using UYTDownloader</p>
      </div>

      {/* Search */}
      <div className="bg-[var(--card)] border border-[var(--card-border)] rounded-xl p-4 mb-6">
        <div className="relative">
          <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--muted)]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search the manual... (e.g., 'merge', 'sponsorblock', 'gpu')"
            className="w-full pl-10 pr-4 py-3 bg-[var(--background)] border border-[var(--card-border)] rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 placeholder:text-[var(--muted)]"
          />
          {search && (
            <button onClick={() => setSearch("")} className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--muted)] hover:text-[var(--foreground)]">&times;</button>
          )}
        </div>
      </div>

      {/* Quick Start FAQs */}
      {filteredFaqs.length > 0 && (
        <div className="bg-[var(--card)] border border-[var(--card-border)] rounded-xl p-5 mb-6">
          <h2 className="text-xs font-medium text-[var(--muted)] mb-4 uppercase tracking-wider">Quick Start Q&amp;A</h2>
          <div className="space-y-2">
            {filteredFaqs.map((faq, i) => (
              <details key={i} className="group">
                <summary className="flex items-center gap-3 px-4 py-3 bg-[var(--background)] rounded-lg cursor-pointer hover:bg-indigo-500/5 transition-colors">
                  <svg className="w-4 h-4 text-indigo-400 flex-shrink-0 transition-transform group-open:rotate-90" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                  </svg>
                  <span className="text-sm font-medium">{faq.q}</span>
                </summary>
                <div className="px-4 py-3 ml-7 text-sm text-[var(--muted)] leading-relaxed">{faq.a}</div>
              </details>
            ))}
          </div>
        </div>
      )}

      {/* Section navigation */}
      <div className="flex flex-wrap gap-2 mb-6">
        {SECTIONS.map((section) => (
          <button
            key={section.id}
            onClick={() => { setActiveSection(activeSection === section.id ? null : section.id); scrollTo(section.id); }}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              activeSection === section.id
                ? "bg-indigo-600 text-white"
                : "bg-[var(--card)] border border-[var(--card-border)] text-[var(--muted)] hover:text-[var(--foreground)] hover:border-[var(--muted)]"
            }`}
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d={section.icon} />
            </svg>
            {section.title}
          </button>
        ))}
      </div>

      {/* Sections */}
      <div className="space-y-6">
        {filtered.map((section) => (
          <div key={section.id} id={section.id} className="bg-[var(--card)] border border-[var(--card-border)] rounded-xl overflow-hidden">
            <div className="px-5 py-4 border-b border-[var(--card-border)] flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-indigo-500/10 flex items-center justify-center">
                <svg className="w-4 h-4 text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d={section.icon} />
                </svg>
              </div>
              <h2 className="text-lg font-semibold">{section.title}</h2>
            </div>
            <div className="divide-y divide-[var(--card-border)]">
              {section.content.map((sub) => (
                <div key={sub.id} id={sub.id} className="px-5 py-5">
                  <h3 className="text-sm font-semibold mb-3 text-indigo-400">{sub.title}</h3>
                  <div className="space-y-1.5">{renderBody(sub.body)}</div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* No results */}
      {filtered.length === 0 && filteredFaqs.length === 0 && (
        <div className="bg-[var(--card)] border border-[var(--card-border)] rounded-xl p-12 text-center text-[var(--muted)]">
          No results for &ldquo;{search}&rdquo;
        </div>
      )}
    </div>
  );
}
