import shutil
import subprocess

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.config import settings
from app.database import engine

app = FastAPI(title="UYTDownloader", version="0.1.3")
app.include_router(api_router)

# Serve downloaded files at /files/
app.mount("/files", StaticFiles(directory=str(settings.output_dir)), name="files")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    checks = {}

    # Database
    try:
        async with engine.connect() as conn:
            await conn.execute(
                __import__("sqlalchemy").text("SELECT 1")
            )
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"

    # Redis
    try:
        import redis
        r = redis.Redis.from_url(settings.redis_url, socket_timeout=2)
        r.ping()
        r.close()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {e}"

    # ffmpeg
    if shutil.which("ffmpeg"):
        try:
            result = subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            version_line = result.stdout.split("\n")[0] if result.stdout else "unknown"
            checks["ffmpeg"] = version_line
        except Exception as e:
            checks["ffmpeg"] = f"error: {e}"
    else:
        checks["ffmpeg"] = "not found"

    # yt-dlp
    try:
        import yt_dlp

        checks["yt_dlp"] = yt_dlp.version.__version__
    except Exception as e:
        checks["yt_dlp"] = f"error: {e}"

    # Directories
    checks["config_dir"] = str(settings.config_dir)
    checks["output_dir"] = str(settings.output_dir)
    checks["work_dir"] = str(settings.work_dir)

    # GPU
    try:
        from app.services.gpu_service import get_gpu_info
        checks["gpu"] = get_gpu_info()
    except Exception as e:
        checks["gpu"] = {"gpu_available": False, "error": str(e)}

    # Download policy
    from app.worker.ytdlp_wrapper import DOWNLOAD_PROFILES
    profile = DOWNLOAD_PROFILES.get(settings.concurrency_mode, {})
    checks["download_policy"] = {
        "mode": settings.concurrency_mode,
        "fragment_concurrency": profile.get("concurrent_fragment_downloads"),
        "request_sleep": profile.get("sleep_requests"),
        "download_sleep": profile.get("sleep_interval"),
        "throttle_detection": f"{profile.get('throttled_rate', 0) // 1000}KB/s",
    }

    # Cookie status
    cookie_path = settings.cookie_path
    if cookie_path and cookie_path.exists():
        import os

        stat = os.stat(cookie_path)
        from datetime import datetime, timezone

        mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        checks["cookies"] = {"present": True, "last_modified": mtime.isoformat()}
    else:
        checks["cookies"] = {"present": False}

    healthy = all(
        v == "ok" or (isinstance(v, str) and "error" not in v)
        for k, v in checks.items()
        if k in ("database", "redis")
    )

    return {"status": "healthy" if healthy else "degraded", "checks": checks}
