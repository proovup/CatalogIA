import pytest
import uuid
import redis as redis_module
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock

from ecoia.services.processing_service import ProcessingService
from ecoia.schemas.processing import (
    ProcessingStatusUpdate,
)


class TestProcessingService:
    """Test cases for ProcessingService"""

    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock()

    @pytest.fixture
    def processing_service(self, mock_db):
        """Processing service instance"""
        with patch("ecoia.services.processing_service.redis.from_url") as mock_from_url:
            mock_from_url.return_value.ping.side_effect = redis_module.ConnectionError("no redis")
            return ProcessingService(mock_db)

    @pytest.fixture
    def sample_document_id(self):
        """Sample document ID"""
        return uuid.uuid4()

    @pytest.mark.asyncio
    async def test_create_processing_status(self, processing_service, mock_db, sample_document_id):
        """Test creating a new processing status"""
        # Arrange
        mock_status = Mock()
        mock_status.id = uuid.uuid4()
        mock_status.document_id = sample_document_id
        mock_status.job_id = "test-job-id"
        mock_status.stage = "upload"
        mock_status.progress = 0
        mock_status.message = "Starting Upload..."
        mock_status.started_at = datetime.utcnow()
        mock_status.completed_at = None
        mock_status.error_details = None
        mock_status.meta_data = None

        with patch(
            "ecoia.services.processing_service.ProcessingStatus",
            return_value=mock_status,
        ):
            # Act
            result = await processing_service.create_processing_status(sample_document_id)

            # Assert
            assert result.document_id == sample_document_id
            assert result.stage == "upload"
            assert result.progress == 0
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_status(self, processing_service, mock_db):
        """Test updating processing status"""
        # Arrange
        job_id = "test-job-id"
        mock_status = Mock()
        mock_status.stage = "upload"
        mock_status.progress = 50
        mock_status.completed_at = None

        mock_db.execute.return_value.scalar_one_or_none.return_value = mock_status

        update_data = ProcessingStatusUpdate(stage="parsing", progress=75, message="Parsing file...")

        # Act
        with (
            patch("ecoia.services.processing_service.ProcessingStatus"),
            patch("ecoia.services.processing_service.select"),
            patch("ecoia.services.processing_service.ProcessingStatusResponse.model_validate", return_value=Mock()),
        ):
            await processing_service.update_status(job_id, update_data)

            # Assert
            mock_db.commit.assert_called_once()
            mock_db.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_progress(self, processing_service, mock_db):
        """Test updating progress"""
        # Arrange
        job_id = "test-job-id"
        mock_status = Mock()
        mock_db.execute.return_value.scalar_one_or_none.return_value = mock_status

        with patch.object(processing_service, "update_status", new_callable=AsyncMock) as mock_update:
            mock_update.return_value = Mock()

            # Act
            await processing_service.update_progress(job_id, 85, "Processing...")

            # Assert
            mock_update.assert_called_once()
            call_args = mock_update.call_args[0]
            assert call_args[0] == job_id
            assert call_args[1].progress == 85
            assert call_args[1].message == "Processing..."

    @pytest.mark.asyncio
    async def test_advance_stage(self, processing_service, mock_db):
        """Test advancing to next stage"""
        # Arrange
        job_id = "test-job-id"
        mock_status = Mock()
        mock_db.execute.return_value.scalar_one_or_none.return_value = mock_status

        with patch.object(processing_service, "update_status", new_callable=AsyncMock) as mock_update:
            mock_update.return_value = Mock()

            # Act
            await processing_service.advance_stage(job_id, "ai_processing", "Starting AI processing...")

            # Assert
            mock_update.assert_called_once()
            call_args = mock_update.call_args[0]
            assert call_args[0] == job_id
            assert call_args[1].stage == "ai_processing"

    @pytest.mark.asyncio
    async def test_fail_processing(self, processing_service, mock_db):
        """Test marking processing as failed"""
        # Arrange
        job_id = "test-job-id"
        mock_status = Mock()
        mock_db.execute.return_value.scalar_one_or_none.return_value = mock_status

        with patch.object(processing_service, "update_status", new_callable=AsyncMock) as mock_update:
            mock_update.return_value = Mock()

            # Act
            await processing_service.fail_processing(job_id, "Parse error", {"line": 10})

            # Assert
            mock_update.assert_called_once()
            call_args = mock_update.call_args[0]
            assert call_args[0] == job_id
            assert call_args[1].stage == "failed"
            assert "Parse error" in call_args[1].message

    @pytest.mark.asyncio
    async def test_complete_processing(self, processing_service, mock_db):
        """Test marking processing as completed"""
        # Arrange
        job_id = "test-job-id"
        mock_status = Mock()
        mock_db.execute.return_value.scalar_one_or_none.return_value = mock_status

        with patch.object(processing_service, "update_status", new_callable=AsyncMock) as mock_update:
            mock_update.return_value = Mock()

            # Act
            await processing_service.complete_processing(job_id, "All done!")

            # Assert
            mock_update.assert_called_once()
            call_args = mock_update.call_args[0]
            assert call_args[0] == job_id
            assert call_args[1].stage == "completed"
            assert call_args[1].progress == 100

    @pytest.mark.asyncio
    async def test_get_status_not_found(self, processing_service, mock_db):
        """Test getting status for non-existent job"""
        # Arrange
        job_id = "non-existent-job"
        mock_db.execute.return_value.scalar_one_or_none.return_value = None

        # Act & Assert
        with patch("ecoia.services.processing_service.select"):
            with pytest.raises(Exception) as exc_info:
                await processing_service.get_status(job_id)

        assert "not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_pipeline_status(self, processing_service, mock_db):
        """Test getting complete pipeline status"""
        # Arrange
        job_id = "test-job-id"
        document_id = uuid.uuid4()

        mock_status = Mock()
        mock_status.job_id = job_id
        mock_status.document_id = document_id
        mock_status.stage = "parsing"
        mock_status.progress = 50
        mock_status.message = "Parsing file..."
        mock_status.started_at = datetime.utcnow()
        mock_status.completed_at = None

        with patch.object(processing_service, "get_status", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_status

            # Act
            result = await processing_service.get_pipeline_status(job_id)

            # Assert
            assert result.job_id == job_id
            assert result.current_stage == "parsing"
            assert result.overall_progress > 0
            assert "parsing" in result.stages
            assert result.stages["parsing"].progress == 50

    @pytest.mark.asyncio
    async def test_get_document_status(self, processing_service, mock_db):
        """Test getting status by document ID"""
        # Arrange
        document_id = uuid.uuid4()
        mock_status = Mock()
        mock_db.execute.return_value.scalar_one_or_none.return_value = mock_status

        with patch("ecoia.services.processing_service.ProcessingStatusResponse.model_validate") as mock_validate:
            mock_validate.return_value = Mock()

            # Act
            await processing_service.get_document_status(document_id)

            # Assert
            mock_db.execute.assert_called_once()
            mock_validate.assert_called_once_with(mock_status)

    @pytest.mark.asyncio
    async def test_list_active_jobs(self, processing_service, mock_db):
        """Test listing active jobs"""
        # Arrange
        mock_jobs = [Mock(), Mock(), Mock()]
        mock_db.execute.return_value.scalars().all.return_value = mock_jobs

        with patch("ecoia.services.processing_service.ProcessingStatusResponse.model_validate") as mock_validate:
            mock_validate.return_value = Mock()

            # Act
            result = await processing_service.list_active_jobs()

            # Assert
            assert len(result) == 3
            mock_db.execute.assert_called_once()

    def test_calculate_overall_progress(self, processing_service):
        """Test overall progress calculation"""
        # Test completed stage
        progress = processing_service._calculate_overall_progress("completed", 100)
        assert progress == 100

        # Test failed stage
        progress = processing_service._calculate_overall_progress("failed", 50)
        assert progress == 50

        # Test middle stage
        progress = processing_service._calculate_overall_progress("parsing", 50)
        assert 0 < progress < 100

        # Test upload stage
        progress = processing_service._calculate_overall_progress("upload", 25)
        assert 0 < progress < 20  # Upload has weight 10, so 25% of 10 = 2.5%

    @pytest.mark.asyncio
    async def test_redis_cache_operations(self, mock_db, sample_document_id):
        """Test Redis cache operations"""
        # Arrange
        mock_redis_client = Mock()
        with patch("ecoia.services.processing_service.redis.from_url", return_value=mock_redis_client) as _:
            service = ProcessingService(mock_db)

            # Test cache update
            mock_status = Mock()
            mock_status.id = uuid.uuid4()
            mock_status.document_id = sample_document_id
            mock_status.job_id = "test-job"
            mock_status.stage = "upload"
            mock_status.progress = 50
            mock_status.message = "Uploading..."
            mock_status.started_at = datetime.utcnow()
            mock_status.completed_at = None
            mock_status.error_details = None

            await service._update_redis_cache("test-job", mock_status)

            # Assert
            mock_redis_client.setex.assert_called_once()

            # Test cache retrieval
            import uuid as _uuid
            from datetime import datetime as _dt

            mock_redis_client.get.return_value = (
                '{"id": "'
                + str(_uuid.uuid4())
                + '", "job_id": "test-job", "document_id": "'
                + str(_uuid.uuid4())
                + '", "stage": "upload", "progress": 50, "message": "Uploading...", "error_details": null, "started_at": "'
                + _dt.utcnow().isoformat()
                + '", "completed_at": null}'
            )

            result = await service._get_from_redis("test-job")

            # Assert
            mock_redis_client.get.assert_called_once()
            assert result is not None
