from fastapi import Depends, FastAPI
from fastapi import File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from src.database import get_session
from src.schemas import AlertItem, FileItem, FileUpdate
from src.service import create_file, delete_file, get_file, get_file_path, list_alerts, list_files, update_file
from src.tasks import process_uploaded_file_task

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/files", response_model=list[FileItem])
async def list_files_view(session: AsyncSession = Depends(get_session)):
    return await list_files(session)


@app.get("/alerts", response_model=list[AlertItem])
async def list_alerts_view(session: AsyncSession = Depends(get_session)):
    return await list_alerts(session)


@app.post("/files", response_model=FileItem, status_code=201)
async def create_file_view(
    title: str = Form(...),
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
):
    file_item = await create_file(session=session, title=title, upload_file=file)
    process_uploaded_file_task.delay(file_item.id)
    return file_item


@app.get("/files/{file_id}", response_model=FileItem)
async def get_file_view(file_id: str, session: AsyncSession = Depends(get_session)):
    return await get_file(session, file_id)


@app.patch("/files/{file_id}", response_model=FileItem)
async def update_file_view(
    file_id: str,
    payload: FileUpdate,
    session: AsyncSession = Depends(get_session),
):
    return await update_file(session=session, file_id=file_id, title=payload.title)


@app.get("/files/{file_id}/download")
async def download_file(file_id: str, session: AsyncSession = Depends(get_session)):
    file_item, stored_path = await get_file_path(session, file_id)
    return FileResponse(
        path=stored_path,
        media_type=file_item.mime_type,
        filename=file_item.original_name,
    )


@app.delete("/files/{file_id}", status_code=204)
async def delete_file_view(file_id: str, session: AsyncSession = Depends(get_session)):
    await delete_file(session, file_id)
