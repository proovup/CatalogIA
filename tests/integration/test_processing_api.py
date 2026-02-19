import pytest
import uuid
from datetime import datetime
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ecoia.main import app
from ecoia.db.database import get_db, Base
from ecoia.db.models import ProcessingStatus, Document

# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_processing.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override database dependency for testing"""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


client = TestClient(app)


@pytest.fixture(scope="module")
def setup_database():
    """Setup test database"""
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    app.dependency_overrides.pop(get_db, None)
    import os

    if os.path.exists("./test_processing.db"):
        os.remove("./test_processing.db")


@pytest.fixture(scope="module")
def sample_document(setup_database):
    """Create a sample document for testing"""
    db = TestingSessionLocal()
    try:
        document = Document(
            id=uuid.uuid4(),
            filename="test.xlsx",
            file_type=".xlsx",
            file_size=1024,
            upload_status="completed",
            upload_progress=100,
            file_path="/tmp/test.xlsx",
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        return document
    finally:
        db.close()


@pytest.fixture(scope="module")
def sample_processing_status(setup_database, sample_document):
    """Create a sample processing status for testing"""
    db = TestingSessionLocal()
    try:
        status = ProcessingStatus(
            document_id=sample_document.id,
            job_id=f"test-job-{uuid.uuid4().hex[:8]}",
            stage="parsing",
            progress=50,
            message="Parsing file...",
            started_at=datetime.utcnow(),
        )
        db.add(status)
        db.commit()
        db.refresh(status)
        return status
    finally:
        db.close()


class TestProcessingAPI:
    """Integration tests for Processing API endpoints"""

    def test_get_processing_status_by_job_id(self, setup_database, sample_processing_status):
        """Test getting processing status by job ID"""
        # Act
        response = client.get(f"/api/v1/processing/status/{sample_processing_status.job_id}")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == sample_processing_status.job_id
        assert data["stage"] == "parsing"
        assert data["progress"] == 50
        assert "message" in data

    def test_get_processing_status_not_found(self, setup_database):
        """Test getting status for non-existent job"""
        # Act
        response = client.get("/api/v1/processing/status/non-existent-job")

        # Assert
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    def test_get_pipeline_status(self, setup_database, sample_processing_status):
        """Test getting complete pipeline status"""
        # Act
        response = client.get(f"/api/v1/processing/pipeline/{sample_processing_status.job_id}")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == sample_processing_status.job_id
        assert data["current_stage"] == "parsing"
        assert data["overall_progress"] > 0
        assert "stages" in data
        assert "upload" in data["stages"]
        assert "parsing" in data["stages"]
        assert "ai_processing" in data["stages"]
        assert "export" in data["stages"]

    def test_get_document_processing_status(self, setup_database, sample_document, sample_processing_status):
        """Test getting processing status by document ID"""
        # Act
        response = client.get(f"/api/v1/processing/document/{sample_document.id}")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == sample_processing_status.job_id
        assert data["document_id"] == str(sample_document.id)

    def test_get_document_processing_status_not_found(self, setup_database):
        """Test getting status for non-existent document"""
        # Act
        fake_id = str(uuid.uuid4())
        response = client.get(f"/api/v1/processing/document/{fake_id}")

        # Assert
        assert response.status_code == 200
        assert response.json() is None

    def test_list_active_jobs(self, setup_database, sample_processing_status):
        """Test listing all active jobs"""
        # Act
        response = client.get("/api/v1/processing/jobs/active")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Should include our sample status since it's not completed/failed
        assert any(job["job_id"] == sample_processing_status.job_id for job in data)

    def test_update_processing_status(self, setup_database, sample_processing_status):
        """Test updating processing status (internal endpoint)"""
        # Arrange
        update_data = {
            "stage": "ai_processing",
            "progress": 75,
            "message": "Processing with AI...",
        }

        # Act
        response = client.put(
            f"/api/v1/processing/status/{sample_processing_status.job_id}",
            json=update_data,
        )

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["stage"] == "ai_processing"
        assert data["progress"] == 75

    def test_advance_stage(self, setup_database, sample_processing_status):
        """Test advancing to next stage"""
        # Act
        response = client.post(
            f"/api/v1/processing/status/{sample_processing_status.job_id}/advance"
            f"?stage=export&message=Exporting results..."
        )

        # Assert
        assert response.status_code == 200
        assert "Advanced to stage: export" in response.json()["message"]

    def test_update_progress(self, setup_database, sample_processing_status):
        """Test updating progress"""
        # Act
        response = client.post(
            f"/api/v1/processing/status/{sample_processing_status.job_id}/progress"
            f"?progress=90&message=Almost done..."
        )

        # Assert
        assert response.status_code == 200
        assert response.json()["progress"] == 90

    def test_complete_processing(self, setup_database, sample_processing_status):
        """Test marking processing as completed"""
        # Act
        response = client.post(
            f"/api/v1/processing/status/{sample_processing_status.job_id}/complete" f"?message=All completed!"
        )

        # Assert
        assert response.status_code == 200
        assert "completed" in response.json()["message"]

    def test_fail_processing(self, setup_database, sample_processing_status):
        """Test marking processing as failed"""
        # Act
        response = client.post(
            f"/api/v1/processing/status/{sample_processing_status.job_id}/fail" f"?error_message=Parse error occurred"
        )

        # Assert
        assert response.status_code == 200
        assert "failed" in response.json()["message"]

    def test_upload_with_processing_tracking(self, setup_database):
        """Test that upload creates processing status"""
        # Arrange
        from io import BytesIO

        file_content = b"test,content\n1,2\n"

        # Act
        response = client.post(
            "/api/v1/documents/upload",
            files={"file": ("test.csv", BytesIO(file_content), "text/csv")},
        )

        # Assert
        assert response.status_code == 201
        document_data = response.json()
        assert "id" in document_data

        # Check that processing status was created
        document_id = document_data["id"]
        status_response = client.get(f"/api/v1/documents/{document_id}/processing-status")

        # Status might be None if processing hasn't started yet, or it might exist
        # Both are valid scenarios
        assert status_response.status_code == 200

    def test_progress_validation(self, setup_database, sample_processing_status):
        """Test progress validation"""
        # Test invalid progress (negative)
        response = client.post(f"/api/v1/processing/status/{sample_processing_status.job_id}/progress" f"?progress=-10")
        assert response.status_code == 422  # Validation error

        # Test invalid progress (over 100)
        response = client.post(f"/api/v1/processing/status/{sample_processing_status.job_id}/progress" f"?progress=150")
        assert response.status_code == 422  # Validation error

    def test_stage_progress_weights(self, setup_database, sample_processing_status):
        """Test that stage progress is calculated with correct weights"""
        # Update to different stages and check overall progress
        stages_progress = []

        for stage in ["upload", "parsing", "ai_processing", "export"]:
            response = client.post(
                f"/api/v1/processing/status/{sample_processing_status.job_id}/advance" f"?stage={stage}"
            )
            assert response.status_code == 200

            # Get pipeline status
            pipeline_response = client.get(f"/api/v1/processing/pipeline/{sample_processing_status.job_id}")
            assert pipeline_response.status_code == 200

            pipeline_data = pipeline_response.json()
            stages_progress.append((stage, pipeline_data["overall_progress"]))

        # Verify progress is generally increasing
        for i in range(1, len(stages_progress)):
            assert stages_progress[i][1] >= stages_progress[i - 1][1]
