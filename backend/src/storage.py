import mimetypes
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from src.config import get_settings


class EmptyUploadError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class StoredUpload:
    file_id: str
    original_name: str
    stored_name: str
    mime_type: str
    size: int
    path: Path


class FileStorage:
    chunk_size = 1024 * 1024

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, stored_name: str) -> Path:
        path = (self.root / Path(stored_name).name).resolve()
        if not path.is_relative_to(self.root.resolve()):
            raise ValueError("Stored file path escapes storage directory")
        return path

    async def save(self, upload_file: UploadFile) -> StoredUpload:
        file_id = str(uuid4())
        original_name = Path(upload_file.filename or "").name or file_id
        stored_name = f"{file_id}{Path(original_name).suffix}"
        stored_path = self.path_for(stored_name)
        size = 0

        try:
            with stored_path.open("wb") as output:
                while chunk := await upload_file.read(self.chunk_size):
                    size += len(chunk)
                    output.write(chunk)

            if size == 0:
                raise EmptyUploadError("File is empty")
        except Exception:
            self.delete(stored_name)
            raise

        return StoredUpload(
            file_id=file_id,
            original_name=original_name,
            stored_name=stored_name,
            mime_type=(
                upload_file.content_type
                or mimetypes.guess_type(original_name)[0]
                or "application/octet-stream"
            ),
            size=size,
            path=stored_path,
        )

    def delete(self, stored_name: str) -> None:
        self.path_for(stored_name).unlink(missing_ok=True)


file_storage = FileStorage(get_settings().storage_dir)
