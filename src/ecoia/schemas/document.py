from datetime import datetime
from uuid import UUID
from typing import Optional, List, Dict, Any
from pydantic import BaseModel


class DocumentBase(BaseModel):
    filename: str
    file_type: str
    file_size: int
    mime_type: Optional[str] = None
    upload_status: str = "uploading"
    upload_progress: int = 0
    meta_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None


class DocumentCreate(DocumentBase):
    supplier_id: Optional[UUID] = None


class DocumentResponse(DocumentBase):
    id: UUID
    file_path: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UploadStatusResponse(BaseModel):
    status: str
    progress: int
    message: str


class BatchUploadRequest(BaseModel):
    files: List[
        str
    ]  # This might not be directly used if we use multipart/form-data for
    # multiple files, but keeping it for structure
    supplier_id: Optional[UUID] = None


class UploadSessionBase(BaseModel):
    user_id: Optional[UUID] = None
    status: str = "active"
    files_count: int = 0
    total_size: int = 0


class UploadSessionCreate(UploadSessionBase):
    pass


class UploadSessionResponse(UploadSessionBase):
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True
