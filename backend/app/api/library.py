"""Library API: browse, download, and merge completed artifacts."""

from __future__ import annotations

import os
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
    search: str = Query("", description="Filter files by name (case-insensitive)"),
    sort: str = Query("date_desc", description="Sort: date_desc, date_asc, name_asc, name_desc, size_desc, size_asc"),
    file_type: str = Query("all", description="Filter: all, video, audio"),
):
    """List all files in the downloads directory with search, sort, and filter."""
    output_dir = Path(settings.output_dir)
    if not output_dir.exists():
        return {"files": [], "total": 0, "page": page, "per_page": per_page}

    VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".avi", ".mov", ".flv"}
    AUDIO_EXTS = {".mp3", ".m4a", ".opus", ".ogg", ".flac", ".wav", ".aac"}

    all_files = []
    search_lower = search.lower()
    for f in output_dir.iterdir():
        if not f.is_file() or f.name.startswith("."):
            continue
        # Search filter
        if search_lower and search_lower not in f.name.lower():
            continue
        # Type filter
        ext = f.suffix.lower()
        if file_type == "video" and ext not in VIDEO_EXTS:
            continue
        if file_type == "audio" and ext not in AUDIO_EXTS:
            continue

        stat = f.stat()
        all_files.append({
            "filename": f.name,
            "size_bytes": stat.st_size,
            "modified_at": stat.st_mtime,
            "download_url": f"/files/{f.name}",
            "extension": ext,
        })

    # Sort
    if sort == "date_desc":
        all_files.sort(key=lambda x: x["modified_at"], reverse=True)
    elif sort == "date_asc":
        all_files.sort(key=lambda x: x["modified_at"])
    elif sort == "name_asc":
        all_files.sort(key=lambda x: x["filename"].lower())
    elif sort == "name_desc":
        all_files.sort(key=lambda x: x["filename"].lower(), reverse=True)
    elif sort == "size_desc":
        all_files.sort(key=lambda x: x["size_bytes"], reverse=True)
    elif sort == "size_asc":
        all_files.sort(key=lambda x: x["size_bytes"])

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
    if "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    file_path = (Path(settings.output_dir) / filename).resolve()
    if not file_path.is_relative_to(Path(settings.output_dir).resolve()):
        raise HTTPException(status_code=400, detail="Invalid filename")
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
    if "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    file_path = (Path(settings.output_dir) / filename).resolve()
    allowed = Path(settings.output_dir).resolve()
    if not file_path.is_relative_to(allowed):
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    os.unlink(file_path)


class ZipRequest(BaseModel):
    filenames: list[str]
    zip_name: str = "UYTDownloader_Export"


@router.post("/zip")
async def create_zip(req: ZipRequest):
    """Create a zip (store mode, no compression) of selected files for download."""
    import zipfile
    import tempfile

    if not req.filenames:
        raise HTTPException(status_code=400, detail="No files specified")

    output_dir = Path(settings.output_dir)
    safe_name = "".join(c if c.isalnum() or c in " ._-" else "_" for c in req.zip_name)
    zip_path = output_dir / f"{safe_name}.zip"

    # Handle collision
    counter = 1
    base = str(zip_path)
    while zip_path.exists():
        stem, suffix = os.path.splitext(base)
        zip_path = Path(f"{stem}_{counter}{suffix}")
        counter += 1

    try:
        with zipfile.ZipFile(str(zip_path), "w", compression=zipfile.ZIP_STORED) as zf:
            for fname in req.filenames:
                if "/" in fname or "\\" in fname:
                    continue
                fpath = (output_dir / fname).resolve()
                if not fpath.is_relative_to(output_dir.resolve()):
                    continue
                if fpath.exists() and fpath.is_file():
                    zf.write(str(fpath), fname)

        return {
            "filename": zip_path.name,
            "size_bytes": zip_path.stat().st_size,
            "download_url": f"/api/library/download/{zip_path.name}",
            "file_count": len(req.filenames),
        }
    except Exception as e:
        # Clean up on failure
        if zip_path.exists():
            os.unlink(zip_path)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/zip/{filename}", status_code=204)
async def delete_zip(filename: str):
    """Delete a zip file after successful download."""
    if not filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Can only delete zip files via this endpoint")
    if "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    file_path = (Path(settings.output_dir) / filename).resolve()
    if not file_path.is_relative_to(Path(settings.output_dir).resolve()):
        raise HTTPException(status_code=400, detail="Invalid filename")
    if file_path.exists():
        os.unlink(file_path)


class MergeRequest(BaseModel):
    filenames: list[str]
    title: str = "Merged"
    mode: str = "video_chapters"  # video_chapters | video_no_chapters | audio_chapters | audio_no_chapters
    normalize_audio: bool = False


@router.post("/merge")
async def merge_files(req: MergeRequest):
    """Queue a merge of multiple library files. Returns a task ID for polling."""
    if len(req.filenames) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 files to merge")

    output_dir = Path(settings.output_dir)
    input_files = []

    for fname in req.filenames:
        if "/" in fname or "\\" in fname:
            raise HTTPException(status_code=400, detail=f"Invalid filename: {fname}")
        fpath = (output_dir / fname).resolve()
        if not fpath.is_relative_to(output_dir.resolve()):
            raise HTTPException(status_code=400, detail=f"Invalid filename: {fname}")
        if not fpath.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {fname}")
        input_files.append(str(fpath))

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

    from app.worker.tasks import run_library_merge
    task = run_library_merge.delay(input_files, out_path, req.mode, req.normalize_audio)

    return {"task_id": task.id, "status": "queued", "output_filename": os.path.basename(out_path)}


@router.get("/merge/{task_id}")
async def get_merge_status(task_id: str):
    """Poll merge task status."""
    from app.celery_app import celery_app
    result = celery_app.AsyncResult(task_id)
    if result.state == "PENDING":
        return {"task_id": task_id, "status": "queued"}
    elif result.state == "STARTED" or result.state == "PROGRESS":
        meta = result.info or {}
        return {"task_id": task_id, "status": "running", "progress": meta.get("progress", 0), "stage": meta.get("stage", "preparing")}
    elif result.state == "SUCCESS":
        data = result.result or {}
        return {"task_id": task_id, "status": "completed", **data}
    else:
        return {"task_id": task_id, "status": "failed", "error": str(result.info)}
