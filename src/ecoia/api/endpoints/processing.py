from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from uuid import UUID

from ecoia.db.database import get_db
from ecoia.services.processing_service import ProcessingService
from ecoia.schemas.processing import (
    ProcessingStatusResponse,
    ProcessingPipelineStatus,
    ProcessingStatusUpdate,
)

router = APIRouter(prefix="/processing", tags=["processing"])


def get_processing_service(db: Session = Depends(get_db)) -> ProcessingService:
    """Dependency to get processing service"""
    return ProcessingService(db)


@router.get("/status/{job_id}", response_model=ProcessingStatusResponse)
async def get_processing_status(
    job_id: str, service: ProcessingService = Depends(get_processing_service)
):
    """Get current processing status for a job"""
    return await service.get_status(job_id)


@router.get("/pipeline/{job_id}", response_model=ProcessingPipelineStatus)
async def get_pipeline_status(
    job_id: str, service: ProcessingService = Depends(get_processing_service)
):
    """Get complete pipeline status with all stages"""
    return await service.get_pipeline_status(job_id)


@router.get(
    "/document/{document_id}", response_model=Optional[ProcessingStatusResponse]
)
async def get_document_status(
    document_id: UUID, service: ProcessingService = Depends(get_processing_service)
):
    """Get processing status for a document"""
    return await service.get_document_status(document_id)


@router.get("/jobs/active", response_model=List[ProcessingStatusResponse])
async def list_active_jobs(
    service: ProcessingService = Depends(get_processing_service),
):
    """List all currently active processing jobs"""
    return await service.list_active_jobs()


@router.put("/status/{job_id}", response_model=ProcessingStatusResponse)
async def update_processing_status(
    job_id: str,
    update_data: ProcessingStatusUpdate,
    service: ProcessingService = Depends(get_processing_service),
):
    """Update processing status (internal use)"""
    return await service.update_status(job_id, update_data)


@router.post("/status/{job_id}/advance")
async def advance_stage(
    job_id: str,
    stage: str = Query(..., description="Next stage to advance to"),
    message: Optional[str] = Query(None, description="Optional status message"),
    service: ProcessingService = Depends(get_processing_service),
):
    """Advance processing to the next stage (internal use)"""
    await service.advance_stage(job_id, stage, message)
    return {"message": f"Advanced to stage: {stage}"}


@router.post("/status/{job_id}/progress")
async def update_progress(
    job_id: str,
    progress: int = Query(..., ge=0, le=100, description="Progress percentage (0-100)"),
    message: Optional[str] = Query(None, description="Optional status message"),
    service: ProcessingService = Depends(get_processing_service),
):
    """Update progress percentage (internal use)"""
    await service.update_progress(job_id, progress, message)
    return {"progress": progress}


@router.post("/status/{job_id}/complete")
async def complete_processing(
    job_id: str,
    message: Optional[str] = Query(None, description="Optional completion message"),
    service: ProcessingService = Depends(get_processing_service),
):
    """Mark processing as completed (internal use)"""
    await service.complete_processing(job_id, message)
    return {"message": "Processing completed"}


@router.post("/status/{job_id}/fail")
async def fail_processing(
    job_id: str,
    error_message: str = Query(..., description="Error message"),
    error_details: Optional[str] = Query(
        None, description="Detailed error information (JSON string)"
    ),
    service: ProcessingService = Depends(get_processing_service),
):
    """Mark processing as failed (internal use)"""
    # Parse error_details from JSON string if provided
    parsed_details = None
    if error_details:
        import json

        try:
            parsed_details = json.loads(error_details)
        except json.JSONDecodeError:
            parsed_details = {"error": "Invalid JSON in error_details"}

    await service.fail_processing(job_id, error_message, parsed_details)
    return {"message": "Processing marked as failed"}
