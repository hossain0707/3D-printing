"""Explicit runtime configuration; production cannot start with demo secrets."""
from dataclasses import dataclass
import os
from pathlib import Path


def _boolean(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes"}


@dataclass(frozen=True)
class Settings:
    environment: str
    data_dir: Path
    token_pepper: str
    admin_key: str
    public_generation: bool
    allowed_origins: tuple[str, ...]

    @classmethod
    def load(cls) -> "Settings":
        environment = os.getenv("MINIMO_ENV", "development").strip().lower()
        token_pepper = os.getenv("MINIMO_TOKEN_PEPPER", "")
        admin_key = os.getenv("MINIMO_ADMIN_KEY", "")
        if environment == "production":
            if len(token_pepper) < 32 or len(admin_key) < 32:
                raise RuntimeError("Production requires MINIMO_TOKEN_PEPPER and MINIMO_ADMIN_KEY (32+ chars each)")
        else:
            token_pepper = token_pepper or "development-only-pepper-not-for-production"
        data = Path(os.getenv("MINIMO_DATA_DIR", "./data")).resolve()
        origins = tuple(o.strip().rstrip("/") for o in os.getenv(
            "MINIMO_ALLOWED_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000"
        ).split(",") if o.strip())
        if any(o == "*" for o in origins):
            raise RuntimeError("Wildcard CORS origins are not permitted")
        return cls(environment, data, token_pepper, admin_key,
                   _boolean("MINIMO_PUBLIC_GENERATION", False), origins)
