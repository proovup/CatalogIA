import pytest
import tempfile
import os
from uuid import uuid4
from unittest.mock import Mock, patch

from ecoia.services.supplier_service import SupplierService
from ecoia.services.config_validator import ConfigValidator
from ecoia.schemas.supplier import (
    SupplierCreate,
    SupplierUpdate,
    SupplierConfig,
    FileConfig,
    ColumnMapping,
    PriceRule,
)


class TestSupplierService:
    """Test cases for SupplierService"""

    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock()

    @pytest.fixture
    def supplier_service(self, mock_db):
        """Supplier service instance"""
        return SupplierService(mock_db)

    @pytest.fixture
    def sample_supplier_config(self):
        """Sample supplier configuration"""
        return SupplierConfig(
            file_config=FileConfig(file_type="csv", delimiter=",", encoding="utf-8", has_header=True),
            column_mappings=[
                ColumnMapping(source="ref", target="sku", required=True),
                ColumnMapping(source="nom", target="product_name", required=True),
                ColumnMapping(source="prix", target="price", required=True),
            ],
            price_rules={"retail": PriceRule(type="percentage", value=1.2)},
        )

    @pytest.mark.asyncio
    async def test_create_supplier_success(self, supplier_service, mock_db, sample_supplier_config):
        """Test successful supplier creation"""
        # Arrange
        supplier_data = SupplierCreate(
            name="Test Supplier",
            description="Test description",
            config=sample_supplier_config,
        )

        mock_db.execute.return_value.scalar_one_or_none.return_value = None
        mock_supplier = Mock()
        mock_supplier.id = uuid4()
        mock_supplier.name = supplier_data.name
        mock_supplier.description = supplier_data.description
        mock_supplier.config = sample_supplier_config.model_dump()
        mock_supplier.is_active = "active"
        mock_db.add.return_value = None
        mock_db.commit.return_value = None
        mock_db.refresh.return_value = None

        mock_response = Mock()
        mock_response.name = "Test Supplier"
        mock_response.description = "Test description"

        with (
            patch("ecoia.services.supplier_service.Supplier", return_value=mock_supplier),
            patch(
                "ecoia.services.supplier_service.SupplierResponse.model_validate",
                return_value=mock_response,
            ),
            patch("ecoia.services.supplier_service.select"),
        ):
            # Act
            result = await supplier_service.create_supplier(supplier_data)

            # Assert
            assert result.name == "Test Supplier"
            assert result.description == "Test description"
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_supplier_duplicate_name(self, supplier_service, mock_db):
        """Test creating supplier with duplicate name"""
        # Arrange
        supplier_data = SupplierCreate(name="Existing Supplier")
        mock_db.execute.return_value.scalar_one_or_none.return_value = Mock()

        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            await supplier_service.create_supplier(supplier_data)

        assert "already exists" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_supplier_not_found(self, supplier_service, mock_db):
        """Test getting non-existent supplier"""
        # Arrange
        supplier_id = uuid4()
        mock_db.execute.return_value.scalar_one_or_none.return_value = None

        # Act & Assert
        with pytest.raises(Exception) as exc_info:
            await supplier_service.get_supplier(supplier_id)

        assert "not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_update_supplier_success(self, supplier_service, mock_db):
        # Arrange
        supplier_id = uuid4()
        mock_supplier = Mock()
        mock_supplier.id = supplier_id
        mock_supplier.name = "Old Name"
        mock_db.execute.return_value.scalar_one_or_none.return_value = mock_supplier

        update_data = SupplierUpdate(name="New Name")

        # Act - execute returns: supplier found, no name conflict
        mock_db.execute.return_value.scalar_one_or_none.side_effect = [
            mock_supplier,  # get_supplier check
            None,  # name conflict check
        ]
        with patch(
            "ecoia.services.supplier_service.SupplierResponse.model_validate",
            return_value=Mock(),
        ):
            await supplier_service.update_supplier(supplier_id, update_data)

        # Assert
        mock_db.execute.assert_called()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_supplier_success(self, supplier_service, mock_db):
        """Test successful supplier deletion"""
        # Arrange
        supplier_id = uuid4()
        mock_supplier = Mock()
        mock_db.execute.return_value.scalar_one_or_none.return_value = mock_supplier

        # delete_supplier: first execute returns supplier, second returns scalar=0 (no docs)
        mock_db.execute.return_value.scalar_one_or_none.return_value = mock_supplier
        mock_db.execute.return_value.scalar.return_value = 0

        # Act
        result = await supplier_service.delete_supplier(supplier_id)

        # Assert
        assert result is True
        mock_db.commit.assert_called_once()


class TestConfigValidator:
    """Test cases for ConfigValidator"""

    def test_validate_config_success(self):
        """Test successful configuration validation"""
        # Arrange
        config_dict = {
            "file_config": {
                "file_type": "csv",
                "delimiter": ",",
                "encoding": "utf-8",
                "has_header": True,
            },
            "column_mappings": [{"source": "ref", "target": "sku", "required": True, "transform": None}],
            "date_format": "%Y-%m-%d",
            "skip_rows": 0,
            "max_errors": 100,
        }

        # Act
        is_valid, errors = ConfigValidator.validate_config(config_dict)

        # Assert
        assert is_valid is True
        assert len(errors) == 0

    def test_validate_config_invalid(self):
        """Test invalid configuration validation"""
        # Arrange
        config_dict = {
            "file_config": {"file_type": "invalid_type"},
            "column_mappings": [],  # Empty mappings should fail
        }

        # Act
        is_valid, errors = ConfigValidator.validate_config(config_dict)

        # Assert
        assert is_valid is False
        assert len(errors) > 0

    def test_validate_column_mappings_success(self):
        """Test successful column mapping validation"""
        # Arrange
        mappings = [
            ColumnMapping(source="ref", target="sku", required=True),
            ColumnMapping(source="name", target="product_name", required=False),
        ]
        available_columns = ["ref", "name", "price"]

        # Act
        is_valid, errors, warnings = ConfigValidator.validate_column_mappings(mappings, available_columns)

        # Assert
        assert is_valid is True
        assert len(errors) == 0
        assert len(warnings) > 0  # Should warn about unmapped 'price' column

    def test_validate_column_mappings_missing_column(self):
        """Test column mapping validation with missing column"""
        # Arrange
        mappings = [ColumnMapping(source="missing", target="sku", required=True)]
        available_columns = ["ref", "name"]

        # Act
        is_valid, errors, warnings = ConfigValidator.validate_column_mappings(mappings, available_columns)

        # Assert
        assert is_valid is False
        assert len(errors) > 0
        assert "not found" in errors[0]

    def test_validate_price_rules_success(self):
        """Test successful price rule validation"""
        # Arrange
        rules = {
            "retail": PriceRule(type="percentage", value=1.2),
            "fixed_price": PriceRule(type="fixed", value=10.0),
        }

        # Act
        is_valid, errors = ConfigValidator.validate_price_rules(rules)

        # Assert
        assert is_valid is True
        assert len(errors) == 0

    def test_validate_price_rules_invalid(self):
        """Test invalid price rule validation"""
        # Arrange
        rules = {"invalid": PriceRule(type="invalid_type", value=None)}

        # Act
        is_valid, errors = ConfigValidator.validate_price_rules(rules)

        # Assert
        assert is_valid is False
        assert len(errors) > 0

    def test_validate_file_config_csv(self):
        """Test CSV file configuration validation"""
        # Arrange
        config = FileConfig(file_type="csv", delimiter=",", encoding="utf-8", has_header=True)

        # Act
        is_valid, errors = ConfigValidator.validate_file_config(config)

        # Assert
        assert is_valid is True
        assert len(errors) == 0

    def test_validate_file_config_invalid_type(self):
        """Test invalid file type validation"""
        # Arrange
        config = FileConfig(file_type="invalid")

        # Act
        is_valid, errors = ConfigValidator.validate_file_config(config)

        # Assert
        assert is_valid is False
        assert len(errors) > 0

    def test_generate_config_template(self):
        """Test configuration template generation"""
        # Act
        template = ConfigValidator.generate_config_template("csv")

        # Assert
        assert "file_config" in template
        assert template["file_config"]["file_type"] == "csv"
        assert "column_mappings" in template
        assert len(template["column_mappings"]) > 0
        assert "price_rules" in template

    def test_test_config_with_sample_csv(self):
        """Test configuration with sample CSV file"""
        # Arrange
        config = SupplierConfig(
            file_config=FileConfig(file_type="csv", delimiter=",", encoding="utf-8", has_header=True),
            column_mappings=[
                ColumnMapping(source="ref", target="sku", required=True),
                ColumnMapping(source="name", target="product_name", required=True),
            ],
        )

        # Create temporary CSV file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write("ref,name,price\n")
            f.write("001,Product 1,10.99\n")
            f.write("002,Product 2,20.50\n")
            temp_file = f.name

        try:
            # Act
            is_valid, errors, warnings, sample_data = ConfigValidator.test_config_with_sample(config, temp_file)

            # Assert
            assert is_valid is True
            assert len(errors) == 0
            assert sample_data is not None
            assert len(sample_data) == 2
        finally:
            os.unlink(temp_file)
