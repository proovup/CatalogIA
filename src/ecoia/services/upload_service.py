import os
import aiofiles
import uuid
from typing import List, Optional
from fastapi import UploadFile, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime

from ecoia.config import settings
from ecoia.db.models import Document
from ecoia.services.processing_service import ProcessingService


class FileUploadService:
    ALLOWED_EXTENSIONS = {
        ".xlsx",
        ".xls",  # Excel
        ".pdf",  # PDF
        ".doc",  # Word legacy
        ".docx",  # Word
        ".txt",
        ".csv",  # Text
        ".md",
        ".markdown",
    }

    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

    def __init__(self, db: Session):
        self.db = db
        self.upload_dir = settings.UPLOAD_DIR
        os.makedirs(self.upload_dir, exist_ok=True)

    def validate_file(self, file: UploadFile):
        # Check extension
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in self.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(f"File type {ext} not supported. Allowed: " f"{', '.join(self.ALLOWED_EXTENSIONS)}"),
            )

        # Check size (Note: file.size might not be available depending on spooling,
        # but we can check content-length header if available or check during read)
        # simplistic check if Content-Length header is present
        # Ideally, we should read chunks and count.
        pass

    async def save_file(self, file: UploadFile, supplier_id: Optional[uuid.UUID] = None) -> Document:
        self.validate_file(file)

        file_id = uuid.uuid4()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_filename = f"{timestamp}_{file_id}_{file.filename}"
        file_path = os.path.join(self.upload_dir, safe_filename)

        # Create processing status tracker
        processing_service = ProcessingService(self.db)
        processing_status = await processing_service.create_processing_status(document_id=file_id, stage="upload")

        file_size = 0
        try:
            # Update progress to 10% - starting upload
            await processing_service.update_progress(processing_status.job_id, 10, "Starting file upload...")

            async with aiofiles.open(file_path, "wb") as out_file:
                total_size = 0
                # Get total file size if available
                if hasattr(file, "size") and file.size:
                    total_size = file.size

                bytes_written = 0
                while content := await file.read(1024 * 1024):  # Read in 1MB chunks
                    file_size += len(content)
                    bytes_written += len(content)

                    # Update progress based on bytes written
                    if total_size > 0:
                        progress = 10 + int((bytes_written / total_size) * 40)  # 10-50% for upload
                        await processing_service.update_progress(
                            processing_status.job_id,
                            min(progress, 50),
                            f"Uploading file... {bytes_written}/{total_size} bytes",
                        )

                    if file_size > self.MAX_FILE_SIZE:
                        # Clean up partial file
                        await out_file.close()
                        os.remove(file_path)
                        size_mb = self.MAX_FILE_SIZE / 1024 / 1024
                        await processing_service.fail_processing(
                            processing_status.job_id,
                            f"File size exceeds limit of {size_mb}MB",
                        )
                        raise HTTPException(
                            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                            detail=(f"File size exceeds limit of {size_mb}MB"),
                        )
                    await out_file.write(content)
        except Exception as e:
            if os.path.exists(file_path):
                os.remove(file_path)
            await processing_service.fail_processing(processing_status.job_id, f"Failed to save file: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")

        # Create database record
        db_document = Document(
            id=file_id,
            supplier_id=supplier_id,
            filename=file.filename,
            file_type=os.path.splitext(file.filename)[1].lower(),
            file_size=file_size,
            mime_type=file.content_type,
            upload_status="completed",
            upload_progress=100,
            status="uploaded",
            file_path=file_path,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        self.db.add(db_document)
        self.db.commit()
        self.db.refresh(db_document)

        # Mark upload as completed
        await processing_service.advance_stage(
            processing_status.job_id,
            "parsing",
            "File uploaded successfully, starting parsing...",
        )

        # Store job_id in document meta_data for reference
        if not db_document.meta_data:
            db_document.meta_data = {}
        db_document.meta_data["job_id"] = processing_status.job_id
        self.db.commit()

        return db_document

    async def batch_upload(self, files: List[UploadFile], supplier_id: Optional[uuid.UUID] = None) -> List[Document]:
        uploaded_documents = []
        errors = []

        for file in files:
            try:
                doc = await self.save_file(file, supplier_id)
                uploaded_documents.append(doc)
            except Exception as e:
                errors.append({"filename": file.filename, "error": str(e)})

        if errors and not uploaded_documents:
            # If all failed
            raise HTTPException(status_code=400, detail=f"All uploads failed: {errors}")

        return uploaded_documents

    def get_upload_status(self, document_id: uuid.UUID) -> dict:
        doc = self.db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        return {
            "status": doc.upload_status,
            "progress": doc.upload_progress,
            "message": doc.error_message if doc.error_message else "Upload processed",
        }

    async def get_processing_status(self, document_id: uuid.UUID):
        """Get full processing status for a document"""
        processing_service = ProcessingService(self.db)
        return await processing_service.get_document_status(document_id)
