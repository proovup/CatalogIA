import pytest
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ecoia.main import app
from ecoia.db.database import get_db, Base

# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_supplier.db"
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

    if os.path.exists("./test_supplier.db"):
        os.remove("./test_supplier.db")


@pytest.fixture
def sample_supplier_config():
    """Sample supplier configuration for testing"""
    return {
        "file_config": {
            "file_type": "csv",
            "delimiter": ",",
            "encoding": "utf-8",
            "has_header": True,
        },
        "column_mappings": [
            {
                "source": "reference",
                "target": "sku",
                "required": True,
                "transform": None,
            },
            {
                "source": "product_name",
                "target": "name",
                "required": True,
                "transform": None,
            },
            {
                "source": "price_ht",
                "target": "price",
                "required": True,
                "transform": None,
            },
        ],
        "price_rules": {"price_ttc": {"type": "percentage", "value": 1.2, "formula": None}},
        "date_format": "%Y-%m-%d",
        "skip_rows": 0,
        "max_errors": 100,
    }


class TestSupplierAPI:
    """Integration tests for Supplier API endpoints"""

    def test_create_supplier_success(self, setup_database, sample_supplier_config):
        """Test successful supplier creation via API"""
        # Arrange
        supplier_data = {
            "name": "Test Supplier API",
            "description": "Test supplier created via API",
            "config": sample_supplier_config,
            "is_active": "active",
        }

        # Act
        response = client.post("/api/v1/suppliers/", json=supplier_data)

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Supplier API"
        assert data["description"] == "Test supplier created via API"
        assert data["config"] is not None
        assert "id" in data

    def test_create_supplier_duplicate_name(self, setup_database, sample_supplier_config):
        """Test creating supplier with duplicate name"""
        # Arrange - Create first supplier
        supplier_data = {"name": "Duplicate Test", "config": sample_supplier_config}
        client.post("/api/v1/suppliers/", json=supplier_data)

        # Act - Try to create duplicate
        response = client.post("/api/v1/suppliers/", json=supplier_data)

        # Assert
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]

    def test_create_supplier_invalid_config(self, setup_database):
        """Test creating supplier with invalid configuration"""
        # Arrange
        supplier_data = {
            "name": "Invalid Config Supplier",
            "config": {
                "file_config": {"file_type": "invalid"},
                "column_mappings": [],  # Empty mappings should fail
            },
        }

        # Act
        response = client.post("/api/v1/suppliers/", json=supplier_data)

        # Assert
        assert response.status_code == 422  # Validation error

    def test_get_suppliers(self, setup_database, sample_supplier_config):
        """Test getting list of suppliers"""
        # Arrange - Create test suppliers
        for i in range(3):
            supplier_data = {"name": f"Supplier {i}", "config": sample_supplier_config}
            client.post("/api/v1/suppliers/", json=supplier_data)

        # Act
        response = client.get("/api/v1/suppliers/")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "suppliers" in data
        assert "total" in data
        assert len(data["suppliers"]) >= 3

    def test_get_suppliers_pagination(self, setup_database, sample_supplier_config):
        """Test supplier list pagination"""
        # Arrange - Create test suppliers
        for i in range(5):
            supplier_data = {
                "name": f"Paginated Supplier {i}",
                "config": sample_supplier_config,
            }
            client.post("/api/v1/suppliers/", json=supplier_data)

        # Act
        response = client.get("/api/v1/suppliers/?skip=0&limit=2")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data["suppliers"]) == 2
        assert data["page"] == 1
        assert data["size"] == 2

    def test_get_supplier_by_id(self, setup_database, sample_supplier_config):
        """Test getting supplier by ID"""
        # Arrange - Create supplier
        supplier_data = {"name": "Get By ID Test", "config": sample_supplier_config}
        create_response = client.post("/api/v1/suppliers/", json=supplier_data)
        supplier_id = create_response.json()["id"]

        # Act
        response = client.get(f"/api/v1/suppliers/{supplier_id}")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == supplier_id
        assert data["name"] == "Get By ID Test"

    def test_get_supplier_not_found(self, setup_database):
        """Test getting non-existent supplier"""
        # Act
        fake_id = str(uuid4())
        response = client.get(f"/api/v1/suppliers/{fake_id}")

        # Assert
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    def test_get_supplier_by_name(self, setup_database, sample_supplier_config):
        """Test getting supplier by name"""
        # Arrange - Create supplier
        supplier_data = {"name": "Get By Name Test", "config": sample_supplier_config}
        client.post("/api/v1/suppliers/", json=supplier_data)

        # Act
        response = client.get("/api/v1/suppliers/by-name/Get By Name Test")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Get By Name Test"

    def test_update_supplier(self, setup_database, sample_supplier_config):
        """Test updating a supplier"""
        # Arrange - Create supplier
        supplier_data = {
            "name": "Update Test",
            "description": "Original description",
            "config": sample_supplier_config,
        }
        create_response = client.post("/api/v1/suppliers/", json=supplier_data)
        supplier_id = create_response.json()["id"]

        # Act - Update supplier
        update_data = {
            "name": "Updated Test",
            "description": "Updated description",
            "is_active": "inactive",
        }
        response = client.put(f"/api/v1/suppliers/{supplier_id}", json=update_data)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Test"
        assert data["description"] == "Updated description"
        assert data["is_active"] == "inactive"

    def test_delete_supplier(self, setup_database, sample_supplier_config):
        """Test deleting a supplier"""
        # Arrange - Create supplier
        supplier_data = {"name": "Delete Test", "config": sample_supplier_config}
        create_response = client.post("/api/v1/suppliers/", json=supplier_data)
        supplier_id = create_response.json()["id"]

        # Act - Delete supplier
        response = client.delete(f"/api/v1/suppliers/{supplier_id}")

        # Assert
        assert response.status_code == 204

    def test_test_config_success(self, setup_database, sample_supplier_config):
        """Test configuration testing endpoint"""
        # Arrange - Create temporary CSV file
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("reference,product_name,price_ht\n")
            f.write("REF001,Test Product,10.99\n")
            temp_file = f.name

        try:
            # Act
            test_request = {
                "config": sample_supplier_config,
                "sample_file_path": temp_file,
            }
            response = client.post("/api/v1/suppliers/test-config", json=test_request)

            # Assert
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert len(data["errors"]) == 0
            assert len(data["mapped_columns"]) > 0
            assert "sample_data" in data
        finally:
            os.unlink(temp_file)

    def test_test_config_invalid_file(self, setup_database, sample_supplier_config):
        """Test configuration testing with invalid file"""
        # Arrange
        test_request = {
            "config": sample_supplier_config,
            "sample_file_path": "/nonexistent/file.csv",
        }

        # Act
        response = client.post("/api/v1/suppliers/test-config", json=test_request)

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "not found" in data["errors"][0]

    def test_get_active_suppliers_only(self, setup_database, sample_supplier_config):
        """Test filtering only active suppliers"""
        # Arrange - Create active and inactive suppliers
        active_data = {
            "name": "Active Supplier",
            "config": sample_supplier_config,
            "is_active": "active",
        }
        inactive_data = {
            "name": "Inactive Supplier",
            "config": sample_supplier_config,
            "is_active": "inactive",
        }
        client.post("/api/v1/suppliers/", json=active_data)
        client.post("/api/v1/suppliers/", json=inactive_data)

        # Act
        response = client.get("/api/v1/suppliers/?active_only=true")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert all(s["is_active"] == "active" for s in data["suppliers"])
