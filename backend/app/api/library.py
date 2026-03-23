"""Library API: browse, download, and merge completed artifacts."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.config import settings

router = APIRouter(prefix="/api/library", tags=["library"])


@router.get("")
async def list_downloads(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
):
    """List all files in the downloads directory."""
    output_dir = Path(settings.output_dir)
    if not output_dir.exists():
        return {"files": [], "total": 0}

    all_files = []
    for f in sorted(output_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if f.is_file() and not f.name.startswith("."):
            stat = f.stat()
            all_files.append({
                "filename": f.name,
                "size_bytes": stat.st_size,
                "modified_at": stat.st_mtime,
                "download_url": f"/files/{f.name}",
                "extension": f.suffix.lower(),
            })

    total = len(all_files)
    start = (page - 1) * per_page
    end = start + per_page

    return {
        "files": all_files[start:end],
        "total": total,
        "page": page,
        "per_page": per_page,
    }


@router.get("/download/{filename}")
async def download_file(filename: str):
    """Download a specific file from the downloads directory."""
    # Prevent path traversal
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    file_path = Path(settings.output_dir) / filename
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type="application/octet-stream",
    )


@router.delete("/{filename}", status_code=204)
async def delete_file(filename: str):
    """Delete a file from the downloads directory."""
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    file_path = Path(settings.output_dir) / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    os.unlink(file_path)


class MergeRequest(BaseModel):
    filenames: list[str]
    title: str = "Merged"
    mode: str = "video_chapters"  # video_chapters | video_no_chapters | audio_chapters | audio_no_chapters
    normalize_audio: bool = False


@router.post("/merge")
async def merge_files(req: MergeRequest):
    """Merge multiple library files into one. Runs synchronously for simplicity."""
    if len(req.filenames) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 files to merge")

    output_dir = Path(settings.output_dir)
    input_files = []

    for fname in req.filenames:
        if "/" in fname or "\\" in fname or ".." in fname:
            raise HTTPException(status_code=400, detail=f"Invalid filename: {fname}")
        fpath = output_dir / fname
        if not fpath.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {fname}")

        # Get duration via ffprobe
        duration = None
        try:
            probe = subprocess.run(
                ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", str(fpath)],
                capture_output=True, text=True, timeout=10,
            )
            if probe.stdout.strip():
                duration = float(probe.stdout.strip())
        except Exception:
            pass

        input_files.append({
            "path": str(fpath),
            "title": fpath.stem,
            "duration": duration,
        })

    from app.services.compilation_service import build_compilation

    safe_title = "".join(c if c.isalnum() or c in " ._-" else "_" for c in req.title)
    is_audio = req.mode.startswith("audio_")
    ext = ".m4a" if is_audio else ".mp4"
    out_path = str(output_dir / f"{safe_title}{ext}")

    # Handle name collisions
    counter = 1
    base = out_path
    while os.path.exists(out_path):
        stem, suffix = os.path.splitext(base)
        out_path = f"{stem}_{counter}{suffix}"
        counter += 1

    result = build_compilation(input_files, out_path, req.mode, req.normalize_audio)

    if result.get("error"):
        raise HTTPException(status_code=500, detail=result["error"])

    return {
        "filename": os.path.basename(out_path),
        "size_bytes": result.get("size_bytes", 0),
        "chapters": result.get("chapters", 0),
        "output_path": out_path,
    }
