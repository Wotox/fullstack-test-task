from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Alert, StoredFile
from src.processing import build_alert, extract_metadata, scan_file
from src.repositories import AlertRepository, FileRepository
from src.storage import EmptyUploadError, FileStorage, file_storage


def _validated_title(title: str) -> str:
    title = title.strip()
    if not title:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Title is empty")
    if len(title) > 255:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Title is too long")
    return title


async def list_files(session: AsyncSession) -> list[StoredFile]:
    return await FileRepository(session).list()


async def list_alerts(session: AsyncSession) -> list[Alert]:
    return await AlertRepository(session).list()


async def get_file(session: AsyncSession, file_id: str) -> StoredFile:
    file_item = await FileRepository(session).get(file_id)
    if not file_item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
    return file_item


async def create_file(
    session: AsyncSession,
    title: str,
    upload_file: UploadFile,
    storage: FileStorage = file_storage,
) -> StoredFile:
    title = _validated_title(title)

    try:
        uploaded = await storage.save(upload_file)
    except EmptyUploadError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File is empty") from error

    file_item = StoredFile(
        id=uploaded.file_id,
        title=title,
        original_name=uploaded.original_name,
        stored_name=uploaded.stored_name,
        mime_type=uploaded.mime_type,
        size=uploaded.size,
        processing_status="uploaded",
    )

    repository = FileRepository(session)
    repository.add(file_item)

    try:
        await session.commit()
    except Exception:
        await session.rollback()
        storage.delete(uploaded.stored_name)
        raise

    await session.refresh(file_item)
    return file_item


async def update_file(session: AsyncSession, file_id: str, title: str) -> StoredFile:
    file_item = await get_file(session, file_id)
    file_item.title = _validated_title(title)
    await session.commit()
    await session.refresh(file_item)
    return file_item


async def delete_file(
    session: AsyncSession,
    file_id: str,
    storage: FileStorage = file_storage,
) -> None:
    file_item = await get_file(session, file_id)
    stored_name = file_item.stored_name

    await AlertRepository(session).delete_for_file(file_id)
    await FileRepository(session).delete(file_item)
    await session.commit()

    storage.delete(stored_name)


async def get_file_path(
    session: AsyncSession,
    file_id: str,
    storage: FileStorage = file_storage,
) -> tuple[StoredFile, Path]:
    file_item = await get_file(session, file_id)
    stored_path = storage.path_for(file_item.stored_name)
    if not stored_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stored file not found")
    return file_item, stored_path


async def process_uploaded_file(
    session: AsyncSession,
    file_id: str,
    storage: FileStorage = file_storage,
) -> None:
    file_item = await FileRepository(session).get(file_id)
    if not file_item:
        return

    file_item.processing_status = "processing"

    scan_result = scan_file(
        original_name=file_item.original_name,
        mime_type=file_item.mime_type,
        size=file_item.size,
    )
    file_item.scan_status = scan_result.status
    file_item.scan_details = scan_result.details
    file_item.requires_attention = scan_result.requires_attention
    await session.commit()

    try:
        stored_path = storage.path_for(file_item.stored_name)
        if not stored_path.exists():
            file_item.processing_status = "failed"
            file_item.scan_status = file_item.scan_status or "failed"
            file_item.scan_details = "stored file not found during metadata extraction"
        else:
            file_item.metadata_json = extract_metadata(
                original_name=file_item.original_name,
                mime_type=file_item.mime_type,
                size=file_item.size,
                stored_path=stored_path,
            )
            file_item.processing_status = "processed"
    except Exception as error:
        file_item.processing_status = "failed"
        file_item.scan_status = file_item.scan_status or "failed"
        file_item.scan_details = f"processing failed: {error}"

    alert_payload = build_alert(
        processing_status=file_item.processing_status,
        requires_attention=file_item.requires_attention,
        scan_details=file_item.scan_details,
    )
    AlertRepository(session).add(
        Alert(file_id=file_item.id, level=alert_payload.level, message=alert_payload.message)
    )
    await session.commit()
