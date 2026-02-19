import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form, status
from sqlalchemy.orm import Session

from ecoia.db.database import get_db
from ecoia.schemas.document import DocumentResponse, UploadStatusResponse
from ecoia.schemas.processing import ProcessingStatusResponse
from ecoia.services.upload_service import FileUploadService

router = APIRouter(
    prefix="/documents",
    tags=["documents"],
    responses={404: {"description": "Not found"}},
)


@router.post(
    "/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED
)
async def upload_document(
    file: UploadFile = File(...),
    supplier_id: Optional[uuid.UUID] = Form(None),
    db: Session = Depends(get_db),
):
    """
    Upload a single document (PDF, Excel, Word, Text).
    """
    service = FileUploadService(db)
    return await service.save_file(file, supplier_id)


@router.post(
    "/batch-upload",
    response_model=List[DocumentResponse],
    status_code=status.HTTP_201_CREATED,
)
async def batch_upload_documents(
    files: List[UploadFile] = File(...),
    supplier_id: Optional[uuid.UUID] = Form(None),
    db: Session = Depends(get_db),
):
    """
    Upload multiple documents at once.
    """
    service = FileUploadService(db)
    return await service.batch_upload(files, supplier_id)


@router.get("/{document_id}/upload-status", response_model=UploadStatusResponse)
async def get_upload_status(document_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Get the status of an uploaded document.
    """
    service = FileUploadService(db)
    status_info = service.get_upload_status(document_id)
    return status_info


@router.get(
    "/{document_id}/processing-status",
    response_model=Optional[ProcessingStatusResponse],
)
async def get_processing_status(document_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Get the full processing status for a document.
    """
    service = FileUploadService(db)
    return await service.get_processing_status(document_id)
