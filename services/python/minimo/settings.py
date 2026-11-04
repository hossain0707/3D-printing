"""Runtime settings. Public upload and reconstruction are explicitly opt-in."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def enabled(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).lower() in {"true", "1", "yes"}


@dataclass(frozen=True)
class Settings:
    environment: str
    data_dir: Path
    token_pepper: str
    admin_key: str
    enable_uploads: bool
    allowed_origins: tuple[str, ...]
    colmap: str
    blender: str
    max_jobs: int
    data_retention_days: int
    stage_timeout_seconds: int

    @classmethod
    def load(cls) -> "Settings":
        environment = os.getenv("MINIMO_ENV", "development").lower()
        secret = os.getenv("MINIMO_TOKEN_PEPPER", "")
        admin = os.getenv("MINIMO_ADMIN_KEY", "")
        if environment == "production" and (len(secret) < 32 or len(admin) < 32):
            raise RuntimeError("Production requires distinct 32+ character MINIMO_TOKEN_PEPPER and MINIMO_ADMIN_KEY")
        if environment != "production":
            secret = secret or "unsafe-local-test-pepper-never-for-production"
        if secret and admin and secret == admin:
            raise RuntimeError("Project and admin secrets must be different")
        origins = tuple(v.strip().rstrip("/") for v in os.getenv(
            "MINIMO_ALLOWED_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000"
        ).split(",") if v.strip())
        if "*" in origins:
            raise RuntimeError("Wildcard CORS is not permitted")
        return cls(
            environment=environment,
            data_dir=Path(os.getenv("MINIMO_DATA_DIR", "./data")).resolve(),
            token_pepper=secret,
            admin_key=admin,
            enable_uploads=enabled("MINIMO_ENABLE_UPLOADS"),
            allowed_origins=origins,
            colmap=os.getenv("MINIMO_COLMAP_BINARY", "colmap"),
            blender=os.getenv("MINIMO_BLENDER_BINARY", "blender"),
            max_jobs=max(1, int(os.getenv("MINIMO_MAX_QUEUED_JOBS", "4"))),
            data_retention_days=max(1, int(os.getenv("MINIMO_DATA_RETENTION_DAYS", "30"))),
            stage_timeout_seconds=max(120, int(os.getenv("MINIMO_STAGE_TIMEOUT_SECONDS", "7200"))),
        )
