from dataclasses import dataclass
from functools import lru_cache
import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str
    storage_dir: Path
    celery_broker_url: str
    celery_result_backend: str


@lru_cache
def get_settings() -> Settings:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        database_url = (
            f"postgresql+asyncpg://{_required_env('POSTGRES_USER')}:"
            f"{_required_env('POSTGRES_PASSWORD')}@{_required_env('POSTGRES_HOST')}:"
            f"{os.environ.get('POSTGRES_PORT') or os.environ.get('PGPORT') or '5432'}/"
            f"{_required_env('POSTGRES_DB')}"
        )

    broker_url = (
        os.environ.get("CELERY_BROKER_URL")
        or os.environ.get("REDIS_URL")
        or "redis://backend-redis:6379/0"
    )

    return Settings(
        database_url=database_url,
        storage_dir=Path(os.environ.get("FILE_STORAGE_DIR", BASE_DIR / "storage" / "files")),
        celery_broker_url=broker_url,
        celery_result_backend=os.environ.get("CELERY_RESULT_BACKEND", broker_url),
    )
