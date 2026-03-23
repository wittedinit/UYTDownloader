"""Library API: browse and download completed artifacts."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

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
