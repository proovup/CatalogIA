import pytest
from fastapi.testclient import TestClient

# Setup in-memory SQLite for testing
# Note: This might have issues with PostgreSQL specific types like UUID
# We might need to mock those or use a different approach if strict
# PostgreSQL types are used.
# For now, let's try to mock the DB session for unit tests instead of
# full integration with SQLite if possible,
# or use a workaround for UUIDs in SQLite if needed.
# But let's start with a basic setup.


@pytest.fixture(scope="module")
def client():
    from ecoia.main import app

    return TestClient(app)
