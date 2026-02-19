import json
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import select
from fastapi import HTTPException, status

import redis
from ecoia.config import settings
from ecoia.db.models import ProcessingStatus
from ecoia.schemas.processing import (
    ProcessingStatusUpdate,
    ProcessingStatusResponse,
    ProcessingPipelineStatus,
    StageProgress,
    PROCESSING_STAGES,
    STAGE_ORDER,
)


class ProcessingService:
    """Service for managing document processing status"""

    def __init__(self, db: Session):
        self.db = db
        # Initialize Redis connection for real-time updates
        try:
            self.redis_client = redis.from_url(
                settings.REDIS_URL, decode_responses=True
            )
            # Test connection
            self.redis_client.ping()
        except (redis.ConnectionError, AttributeError):
            self.redis_client = None

    async def create_processing_status(
        self, document_id: uuid.UUID, stage: str = "upload"
    ) -> ProcessingStatusResponse:
        """Create a new processing status entry"""
        job_id = str(uuid.uuid4())

        db_status = ProcessingStatus(
            document_id=document_id,
            job_id=job_id,
            stage=stage,
            progress=0,
            message=(
                f"Starting {PROCESSING_STAGES.get(stage, {}).get('name', stage)}..."
            ),
        )

        self.db.add(db_status)
        self.db.commit()
        self.db.refresh(db_status)

        # Update Redis cache
        if self.redis_client:
            await self._update_redis_cache(job_id, db_status)

        return ProcessingStatusResponse.model_validate(db_status)

    async def update_status(
        self, job_id: str, update_data: ProcessingStatusUpdate
    ) -> ProcessingStatusResponse:
        """Update processing status"""
        # Get existing status
        current_status = self.db.execute(
            select(ProcessingStatus).where(ProcessingStatus.job_id == job_id)
        ).scalar_one_or_none()

        if not current_status:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Processing status not found",
            )

        # Update fields
        update_dict = update_data.model_dump(exclude_unset=True)

        # Auto-set completed_at if stage is completed or failed
        if (
            update_data.stage in ["completed", "failed"]
            and not current_status.completed_at
        ):
            update_dict["completed_at"] = datetime.utcnow()

        # Apply updates
        for field, value in update_dict.items():
            setattr(current_status, field, value)

        self.db.commit()
        self.db.refresh(current_status)

        # Update Redis cache
        if self.redis_client:
            await self._update_redis_cache(job_id, current_status)

        return ProcessingStatusResponse.model_validate(current_status)

    async def update_progress(
        self, job_id: str, progress: int, message: Optional[str] = None
    ) -> ProcessingStatusResponse:
        """Update progress percentage"""
        return await self.update_status(
            job_id, ProcessingStatusUpdate(progress=progress, message=message)
        )

    async def advance_stage(
        self, job_id: str, new_stage: str, message: Optional[str] = None
    ) -> ProcessingStatusResponse:
        """Advance to the next processing stage"""
        stage_name = PROCESSING_STAGES.get(new_stage, {}).get("name", new_stage)
        update_data = ProcessingStatusUpdate(
            stage=new_stage,
            message=message or f"Starting {stage_name}...",
        )

        return await self.update_status(job_id, update_data)

    async def fail_processing(
        self,
        job_id: str,
        error_message: str,
        error_details: Optional[Dict[str, Any]] = None,
    ) -> ProcessingStatusResponse:
        """Mark processing as failed"""
        update_data = ProcessingStatusUpdate(
            stage="failed",
            message=f"Processing failed: {error_message}",
            error_details=error_details or {"error": error_message},
        )

        return await self.update_status(job_id, update_data)

    async def complete_processing(
        self, job_id: str, message: Optional[str] = None
    ) -> ProcessingStatusResponse:
        """Mark processing as completed"""
        update_data = ProcessingStatusUpdate(
            stage="completed",
            progress=100,
            message=message or "Processing completed successfully",
        )

        return await self.update_status(job_id, update_data)

    async def get_status(self, job_id: str) -> ProcessingStatusResponse:
        """Get current processing status"""
        # Try Redis first for real-time updates
        if self.redis_client:
            cached = await self._get_from_redis(job_id)
            if cached:
                return cached

        # Fallback to database
        db_status = self.db.execute(
            select(ProcessingStatus).where(ProcessingStatus.job_id == job_id)
        ).scalar_one_or_none()

        if not db_status:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Processing status not found",
            )

        return ProcessingStatusResponse.model_validate(db_status)

    async def get_pipeline_status(self, job_id: str) -> ProcessingPipelineStatus:
        """Get complete pipeline status with all stages"""
        status = await self.get_status(job_id)

        # Calculate stage progress
        stages = {}
        current_stage_index = (
            STAGE_ORDER.index(status.stage) if status.stage in STAGE_ORDER else 0
        )

        for i, stage_name in enumerate(STAGE_ORDER):
            if stage_name in ["completed", "failed"]:
                continue

            stage_info = PROCESSING_STAGES.get(stage_name, {})

            if i < current_stage_index:
                # Completed stage
                stages[stage_name] = StageProgress(
                    stage=stage_name,
                    progress=100,
                    message=f"{stage_info.get('name', stage_name)} completed",
                    completed_at=status.started_at,  # Simplified
                )
            elif i == current_stage_index:
                # Current stage
                stages[stage_name] = StageProgress(
                    stage=stage_name,
                    progress=status.progress,
                    message=status.message,
                    started_at=status.started_at,
                )
            else:
                # Future stage
                stages[stage_name] = StageProgress(
                    stage=stage_name,
                    progress=0,
                    message=f"Waiting for {stage_info.get('name', stage_name)}...",
                )

        # Calculate overall progress
        overall_progress = self._calculate_overall_progress(
            status.stage, status.progress
        )

        return ProcessingPipelineStatus(
            job_id=status.job_id,
            document_id=status.document_id,
            current_stage=status.stage,
            overall_progress=overall_progress,
            stages=stages,
            status=(
                "running"
                if status.stage not in ["completed", "failed"]
                else status.stage
            ),
            started_at=status.started_at,
            completed_at=status.completed_at,
            error_message=status.message if status.stage == "failed" else None,
        )

    async def get_document_status(
        self, document_id: uuid.UUID
    ) -> Optional[ProcessingStatusResponse]:
        """Get processing status for a document"""
        doc_status = self.db.execute(
            select(ProcessingStatus).where(ProcessingStatus.document_id == document_id)
        ).scalar_one_or_none()

        if not doc_status:
            return None

        return ProcessingStatusResponse.model_validate(doc_status)

    async def list_active_jobs(self) -> List[ProcessingStatusResponse]:
        """List all currently active processing jobs"""
        jobs = (
            self.db.execute(
                select(ProcessingStatus)
                .where(ProcessingStatus.stage.notin_(["completed", "failed"]))
                .order_by(ProcessingStatus.started_at.desc())
            )
            .scalars()
            .all()
        )

        return [ProcessingStatusResponse.model_validate(job) for job in jobs]

    async def _update_redis_cache(self, job_id: str, proc_status: ProcessingStatus):
        """Update Redis cache with status"""
        if not self.redis_client:
            return

        cache_key = f"processing_status:{job_id}"
        status_data = {
            "id": str(proc_status.id),
            "document_id": str(proc_status.document_id),
            "job_id": proc_status.job_id,
            "stage": proc_status.stage,
            "progress": proc_status.progress,
            "message": proc_status.message,
            "error_details": proc_status.error_details,
            "started_at": proc_status.started_at.isoformat(),
            "completed_at": (
                proc_status.completed_at.isoformat()
                if proc_status.completed_at
                else None
            ),
        }

        # Cache for 1 hour
        self.redis_client.setex(cache_key, 3600, json.dumps(status_data))

    async def _get_from_redis(self, job_id: str) -> Optional[ProcessingStatusResponse]:
        """Get status from Redis cache"""
        if not self.redis_client:
            return None

        cache_key = f"processing_status:{job_id}"
        cached_data = self.redis_client.get(cache_key)

        if not cached_data:
            return None

        try:
            data = json.loads(cached_data)
            # Convert string dates back to datetime
            if data.get("started_at"):
                data["started_at"] = datetime.fromisoformat(data["started_at"])
            if data.get("completed_at"):
                data["completed_at"] = datetime.fromisoformat(data["completed_at"])

            return ProcessingStatusResponse(**data)
        except (json.JSONDecodeError, ValueError):
            return None

    def _calculate_overall_progress(
        self, current_stage: str, stage_progress: int
    ) -> int:
        """Calculate overall progress based on current stage and progress"""
        if current_stage == "completed":
            return 100
        if current_stage == "failed":
            return stage_progress

        stage_index = (
            STAGE_ORDER.index(current_stage) if current_stage in STAGE_ORDER else 0
        )

        # Calculate weighted progress
        total_weight = sum(info.get("weight", 0) for info in PROCESSING_STAGES.values())
        completed_weight = sum(
            PROCESSING_STAGES.get(STAGE_ORDER[i], {}).get("weight", 0)
            for i in range(stage_index)
            if STAGE_ORDER[i] in PROCESSING_STAGES
        )

        current_stage_weight = PROCESSING_STAGES.get(current_stage, {}).get("weight", 0)
        current_progress_weight = (current_stage_weight * stage_progress) / 100

        overall_progress = int(
            ((completed_weight + current_progress_weight) / total_weight) * 100
        )
        return min(overall_progress, 100)
