from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://uyt:uyt@postgres:5432/uyt"
    database_url_sync: str = "postgresql+psycopg2://uyt:uyt@postgres:5432/uyt"

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # Runtime directories (volume-mounted in Docker)
    config_dir: Path = Path("/config")
    output_dir: Path = Path("/downloads")
    work_dir: Path = Path("/work")

    # Cookie file (Netscape format, refreshed by helper agent)
    cookie_file: str = ""

    # SponsorBlock
    sponsorblock_default: str = "keep"  # keep | mark_chapters | remove
    sponsorblock_api: str = "https://sponsor.ajay.app"

    # Concurrency
    concurrency_mode: str = "balanced"  # safe | balanced | power

    # Server
    port: int = 8000

    # Format snapshot expiry (seconds)
    format_snapshot_ttl: int = 14400  # 4 hours

    model_config = {"env_prefix": "UYT_", "env_file": ".env", "extra": "ignore"}

    @property
    def cookie_path(self) -> Path | None:
        if self.cookie_file:
            return Path(self.cookie_file)
        default = self.config_dir / "cookies" / "youtube.txt"
        if default.exists():
            return default
        return None

    @property
    def incomplete_dir(self) -> Path:
        return self.work_dir / "incomplete"

    @property
    def staging_dir(self) -> Path:
        return self.work_dir / "staging"

    @property
    def log_dir(self) -> Path:
        return self.config_dir / "logs" / "jobs"


settings = Settings()
