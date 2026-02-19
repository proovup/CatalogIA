import pytest
import uuid
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi import UploadFile
from ecoia.services.upload_service import FileUploadService
from ecoia.db.models import Document


# Mock dependencies
@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def service(mock_db):
    # Patch the settings to use a temp dir
    with patch("ecoia.services.upload_service.settings") as mock_settings, patch("os.makedirs"):
        mock_settings.UPLOAD_DIR = "/tmp/test_uploads"
        return FileUploadService(mock_db)


@pytest.mark.asyncio
async def test_upload_valid_file(service, mock_db):
    # Prepare
    content = b"test content"
    filename = "test.txt"

    # Use MagicMock instead of real UploadFile to avoid property setter issues
    file = MagicMock(spec=UploadFile)
    file.filename = filename
    file.content_type = "text/plain"
    file.read = AsyncMock(side_effect=[content, b""])  # Simulate reading content then EOF

    mock_processing_service = MagicMock()
    mock_processing_service.create_processing_status = AsyncMock(return_value=MagicMock(job_id="test-job"))
    mock_processing_service.update_progress = AsyncMock()
    mock_processing_service.advance_stage = AsyncMock()
    mock_processing_service.fail_processing = AsyncMock()

    # Act
    # We need to mock aiofiles.open since it interacts with filesystem
    with (
        patch("aiofiles.open") as mock_open,
        patch("ecoia.services.upload_service.ProcessingService", return_value=mock_processing_service),
    ):
        mock_file = MagicMock()
        mock_file.write = AsyncMock()  # Make write awaitable
        mock_open.return_value.__aenter__.return_value = mock_file

        result = await service.save_file(file)

    # Assert
    assert result.filename == filename
    assert result.upload_status == "completed"
    assert result.file_size == len(content)

    # Check DB interaction
    mock_db.add.assert_called()
    mock_db.commit.assert_called()
    mock_db.refresh.assert_called()


@pytest.mark.asyncio
async def test_validate_file_extension(service):
    # Prepare invalid file
    file = MagicMock(spec=UploadFile)
    file.filename = "test.exe"

    # Act & Assert
    with pytest.raises(Exception) as excinfo:
        await service.save_file(file)

    assert "not supported" in str(excinfo.value)


def test_get_upload_status(service, mock_db):
    # Prepare
    doc_id = uuid.uuid4()
    mock_doc = Document(id=doc_id, upload_status="completed", upload_progress=100)
    mock_db.query.return_value.filter.return_value.first.return_value = mock_doc

    # Act
    status = service.get_upload_status(doc_id)

    # Assert
    assert status["status"] == "completed"
    assert status["progress"] == 100
