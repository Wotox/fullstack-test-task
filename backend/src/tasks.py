import asyncio
from collections.abc import Awaitable
from typing import TypeVar

from celery import Celery

from src.config import get_settings
from src.database import async_session_maker
from src.service import process_uploaded_file


settings = get_settings()
celery_app = Celery(
    "file_tasks",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

T = TypeVar("T")
_worker_loop: asyncio.AbstractEventLoop | None = None


def run_in_worker_loop(coroutine: Awaitable[T]) -> T:
    global _worker_loop
    if _worker_loop is None or _worker_loop.is_closed():
        _worker_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_worker_loop)
    return _worker_loop.run_until_complete(coroutine)


async def _process_uploaded_file(file_id: str) -> None:
    async with async_session_maker() as session:
        await process_uploaded_file(session=session, file_id=file_id)


@celery_app.task
def process_uploaded_file_task(file_id: str) -> None:
    run_in_worker_loop(_process_uploaded_file(file_id))
