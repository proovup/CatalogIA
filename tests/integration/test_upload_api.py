import pytest
import os
import shutil
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from ecoia.main import app
from ecoia.config import settings
from ecoia.db.database import get_db, Base

# Override upload dir for testing
TEST_UPLOAD_DIR = os.path.join(settings.BASE_DIR, "test_uploads")

# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_upload.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="module")
def test_client():
    # Setup DB
    Base.metadata.create_all(bind=engine)
    os.makedirs(TEST_UPLOAD_DIR, exist_ok=True)

    original_upload_dir = settings.UPLOAD_DIR
    settings.UPLOAD_DIR = TEST_UPLOAD_DIR

    client = TestClient(app)
    yield client

    # Teardown
    settings.UPLOAD_DIR = original_upload_dir
    if os.path.exists(TEST_UPLOAD_DIR):
        shutil.rmtree(TEST_UPLOAD_DIR)
    Base.metadata.drop_all(bind=engine)
    if os.path.exists("./test_upload.db"):
        os.remove("./test_upload.db")


def test_upload_flow(test_client):
    # 1. Upload a file
    filename = "integration_test.txt"
    file_content = b"This is a test file for integration testing."

    files = {"file": (filename, file_content, "text/plain")}
    response = test_client.post("/api/v1/documents/upload", files=files)

    assert response.status_code == 201
    data = response.json()
    assert data["filename"] == filename
    assert "id" in data
    doc_id = data["id"]

    # 2. Check status
    response = test_client.get(f"/api/v1/documents/{doc_id}/upload-status")
    assert response.status_code == 200
    status_data = response.json()
    assert status_data["status"] == "completed"
    assert status_data["progress"] == 100

    # 3. Verify file exists on disk
    # Note: The filename generation logic in service includes timestamp
    # which might vary slightly or format.
    # Let's check if we can find the file in the dir
    found_files = os.listdir(TEST_UPLOAD_DIR)
    assert any(doc_id in f for f in found_files)


def test_upload_invalid_file_type(test_client):
    filename = "malicious.exe"
    file_content = b"executable content"

    files = {"file": (filename, file_content, "application/x-msdownload")}
    response = test_client.post("/api/v1/documents/upload", files=files)

    assert response.status_code == 400
    assert "not supported" in response.json()["detail"]


def test_batch_upload(test_client):
    files = [
        ("files", ("batch1.txt", b"content1", "text/plain")),
        ("files", ("batch2.txt", b"content2", "text/plain")),
    ]

    response = test_client.post("/api/v1/documents/batch-upload", files=files)

    assert response.status_code == 201
    data = response.json()
    assert len(data) == 2
    assert data[0]["filename"] == "batch1.txt"
    assert data[1]["filename"] == "batch2.txt"
