from datetime import datetime
from uuid import UUID
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class ProcessingStatusBase(BaseModel):
    """Base processing status schema"""

    document_id: UUID
    job_id: str
    stage: str = Field(..., description="Current processing stage")
    progress: int = Field(default=0, ge=0, le=100, description="Progress percentage")
    message: Optional[str] = Field(default=None, description="Status message")
    error_details: Optional[Dict[str, Any]] = Field(
        default=None, description="Error details if failed"
    )
    meta_data: Optional[Dict[str, Any]] = Field(
        default=None, description="Additional metadata"
    )


class ProcessingStatusCreate(ProcessingStatusBase):
    """Schema for creating processing status"""

    pass


class ProcessingStatusUpdate(BaseModel):
    """Schema for updating processing status"""

    stage: Optional[str] = None
    progress: Optional[int] = Field(default=None, ge=0, le=100)
    message: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None
    completed_at: Optional[datetime] = None


class ProcessingStatusResponse(ProcessingStatusBase):
    """Schema for processing status response"""

    id: UUID
    started_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class StageProgress(BaseModel):
    """Progress information for a specific stage"""

    stage: str
    progress: int
    message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class ProcessingPipelineStatus(BaseModel):
    """Complete pipeline status with all stages"""

    job_id: str
    document_id: UUID
    current_stage: str
    overall_progress: int
    stages: Dict[str, StageProgress]
    status: str  # running, completed, failed
    started_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None


# Processing stage constants
PROCESSING_STAGES = {
    "upload": {
        "name": "Upload",
        "description": "Uploading file to server",
        "weight": 10,
    },
    "parsing": {
        "name": "Parsing",
        "description": "Extracting data from file",
        "weight": 20,
    },
    "ai_processing": {
        "name": "AI Processing",
        "description": "Processing with AI models",
        "weight": 50,
    },
    "export": {
        "name": "Export",
        "description": "Generating output files",
        "weight": 20,
    },
}

STAGE_ORDER = ["upload", "parsing", "ai_processing", "export", "completed", "failed"]
