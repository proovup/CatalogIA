from uuid import UUID
from fastapi import APIRouter, Depends, status, UploadFile, File
from sqlalchemy.orm import Session
import yaml

from ecoia.db.database import get_db
from ecoia.services.format_service import FormatService
from ecoia.schemas.format import (
    FormatCreate,
    FormatUpdate,
    FormatResponse,
    FormatList,
)

router = APIRouter(prefix="/formats", tags=["formats"])


def get_format_service(db: Session = Depends(get_db)) -> FormatService:
    return FormatService(db)


@router.get("/", response_model=FormatList)
async def list_formats(service: FormatService = Depends(get_format_service)):
    return await service.list_formats()


@router.post("/", response_model=FormatResponse, status_code=status.HTTP_201_CREATED)
async def create_format(
    data: FormatCreate,
    service: FormatService = Depends(get_format_service),
):
    return await service.create_format(data)


@router.post("/upload", response_model=FormatResponse, status_code=status.HTTP_201_CREATED)
async def upload_format(
    file: UploadFile = File(...),
    service: FormatService = Depends(get_format_service),
):
    content = await file.read()
    parsed = yaml.safe_load(content)
    if not isinstance(parsed, dict):
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail="Invalid YAML file")

    name = parsed.get("name", parsed.get("description", file.filename or "Untitled"))
    description = parsed.get("description", "")

    data = FormatCreate(name=name, description=description, yaml_content=parsed)
    return await service.create_format(data)


@router.get("/{format_id}", response_model=FormatResponse)
async def get_format(
    format_id: UUID,
    service: FormatService = Depends(get_format_service),
):
    return await service.get_format(format_id)


@router.put("/{format_id}", response_model=FormatResponse)
async def update_format(
    format_id: UUID,
    data: FormatUpdate,
    service: FormatService = Depends(get_format_service),
):
    return await service.update_format(format_id, data)


@router.delete("/{format_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_format(
    format_id: UUID,
    service: FormatService = Depends(get_format_service),
):
    await service.delete_format(format_id)
