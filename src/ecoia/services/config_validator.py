from typing import Dict, Any, List, Optional
import pandas as pd

from ecoia.schemas.supplier import SupplierConfig, ColumnMapping, FileConfig, PriceRule


class ConfigValidator:
    """Service for validating supplier configurations"""

    @staticmethod
    def validate_config(config_dict: Dict[str, Any]) -> tuple[bool, List[str]]:
        """
        Validate a configuration dictionary against the schema

        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []

        try:
            # Try to parse the configuration
            SupplierConfig(**config_dict)
            return True, []
        except Exception as e:
            # Handle validation errors
            if hasattr(e, "errors"):
                for error in e.errors():
                    field = ".".join(str(x) for x in error["loc"])
                    message = error["msg"]
                    errors.append(f"Field '{field}': {message}")
            else:
                errors.append(str(e))
            return False, errors

    @staticmethod
    def validate_column_mappings(
        mappings: List[ColumnMapping], available_columns: List[str]
    ) -> tuple[bool, List[str], List[str]]:
        """
        Validate column mappings against available columns

        Returns:
            Tuple of (is_valid, errors, warnings)
        """
        errors = []
        warnings = []

        # Check if all source columns exist
        for mapping in mappings:
            if mapping.source not in available_columns:
                errors.append(f"Source column '{mapping.source}' not found in file")

        # Check for duplicate target fields
        targets = [m.target for m in mappings]
        duplicates = set([t for t in targets if targets.count(t) > 1])
        if duplicates:
            errors.append(f"Duplicate target fields: {', '.join(duplicates)}")

        # Check for unmapped columns
        mapped_sources = [m.source for m in mappings]
        unmapped = set(available_columns) - set(mapped_sources)
        if unmapped:
            warnings.append(f"Unmapped columns: {', '.join(unmapped)}")

        # Validate required columns
        for mapping in mappings:
            if mapping.required and mapping.source not in available_columns:
                errors.append(f"Required column '{mapping.source}' is missing")

        return len(errors) == 0, errors, warnings

    @staticmethod
    def validate_price_rules(rules: Dict[str, PriceRule]) -> tuple[bool, List[str]]:
        """
        Validate price transformation rules

        Returns:
            Tuple of (is_valid, errors)
        """
        errors = []

        for rule_name, rule in rules.items():
            if rule.type == "fixed":
                if rule.value is None:
                    errors.append(
                        f"Price rule '{rule_name}': fixed type requires a value"
                    )
            elif rule.type == "percentage":
                if rule.value is None:
                    errors.append(
                        f"Price rule '{rule_name}': percentage type requires a value"
                    )
                if rule.value and (rule.value < -100 or rule.value > 1000):
                    errors.append(
                        f"Price rule '{rule_name}': percentage value should be "
                        f"between -100 and 1000"
                    )
            elif rule.type == "formula":
                if not rule.formula:
                    errors.append(
                        f"Price rule '{rule_name}': formula type requires a formula"
                    )
                # Basic formula validation
                if rule.formula and not any(
                    x in rule.formula for x in ["price", "cost", "value"]
                ):
                    errors.append(
                        f"Price rule '{rule_name}': formula should reference "
                        f"price, cost, or value"
                    )
            else:
                errors.append(
                    f"Price rule '{rule_name}': invalid type '{rule.type}'. "
                    f"Must be fixed, percentage, or formula"
                )

        return len(errors) == 0, errors

    @staticmethod
    def validate_file_config(config: FileConfig) -> tuple[bool, List[str]]:
        """
        Validate file configuration

        Returns:
            Tuple of (is_valid, errors)
        """
        errors = []

        # Validate file type
        supported_types = ["csv", "xlsx", "xls", "txt"]
        if config.file_type.lower() not in supported_types:
            errors.append(
                f"Unsupported file type '{config.file_type}'. "
                f"Supported types: {', '.join(supported_types)}"
            )

        # Validate CSV specific settings
        if config.file_type.lower() == "csv":
            if not config.delimiter:
                errors.append("CSV files require a delimiter")
            if config.delimiter and len(config.delimiter) != 1:
                errors.append("CSV delimiter must be a single character")

        # Validate Excel specific settings
        if config.file_type.lower() in ["xlsx", "xls"]:
            if config.delimiter:
                errors.append("Delimiter is not used for Excel files")

        # Validate encoding
        try:
            "test".encode(config.encoding)
        except LookupError:
            errors.append(f"Invalid encoding '{config.encoding}'")

        return len(errors) == 0, errors

    @staticmethod
    def test_config_with_sample(
        config: SupplierConfig, sample_file_path: str, max_rows: int = 10
    ) -> tuple[bool, List[str], List[str], Optional[pd.DataFrame]]:
        """
        Test configuration with a sample file

        Returns:
            Tuple of (is_valid, errors, warnings, sample_data)
        """
        errors = []
        warnings = []
        sample_data = None

        try:
            # Read file based on configuration
            if config.file_config.file_type.lower() == "csv":
                df = pd.read_csv(
                    sample_file_path,
                    delimiter=config.file_config.delimiter,
                    encoding=config.file_config.encoding,
                    header=0 if config.file_config.has_header else None,
                    skiprows=config.skip_rows,
                    nrows=max_rows,
                )
            elif config.file_config.file_type.lower() in ["xlsx", "xls"]:
                df = pd.read_excel(
                    sample_file_path,
                    sheet_name=config.file_config.sheet_name or 0,
                    header=0 if config.file_config.has_header else None,
                    skiprows=config.skip_rows,
                    nrows=max_rows,
                )
            else:
                errors.append(
                    f"Unsupported file type for testing: {config.file_config.file_type}"
                )
                return False, errors, warnings, None

            # Validate column mappings
            available_columns = df.columns.tolist()
            is_valid, map_errors, map_warnings = (
                ConfigValidator.validate_column_mappings(
                    config.column_mappings, available_columns
                )
            )
            errors.extend(map_errors)
            warnings.extend(map_warnings)

            # Check data quality
            for mapping in config.column_mappings:
                if mapping.source in available_columns:
                    col_data = df[mapping.source]

                    # Check for empty required columns
                    if mapping.required and col_data.isnull().all():
                        errors.append(
                            f"Required column '{mapping.source}' is completely empty"
                        )

                    # Check for high null percentage
                    null_pct = (col_data.isnull().sum() / len(col_data)) * 100
                    if null_pct > 50:
                        warnings.append(
                            f"Column '{mapping.source}' has {null_pct:.1f}% null values"
                        )

            sample_data = df

        except pd.errors.EmptyDataError:
            errors.append("File is empty or has no valid data")
        except pd.errors.ParserError as e:
            errors.append(f"Error parsing file: {str(e)}")
        except UnicodeDecodeError:
            errors.append(
                "Encoding error. Try a different encoding (e.g., latin-1, cp1252)"
            )
        except Exception as e:
            errors.append(f"Unexpected error: {str(e)}")

        return len(errors) == 0, errors, warnings, sample_data

    @staticmethod
    def generate_config_template(file_type: str = "csv") -> Dict[str, Any]:
        """
        Generate a configuration template for a given file type

        Returns:
            Configuration dictionary template
        """
        template = {
            "file_config": {
                "file_type": file_type,
                "delimiter": "," if file_type == "csv" else None,
                "encoding": "utf-8",
                "has_header": True,
                "sheet_name": None if file_type != "xlsx" else "Sheet1",
            },
            "column_mappings": [
                {
                    "source": "reference",
                    "target": "sku",
                    "required": True,
                    "transform": None,
                },
                {
                    "source": "name",
                    "target": "product_name",
                    "required": True,
                    "transform": None,
                },
                {
                    "source": "price",
                    "target": "price",
                    "required": True,
                    "transform": None,
                },
                {
                    "source": "description",
                    "target": "description",
                    "required": False,
                    "transform": None,
                },
            ],
            "price_rules": {
                "retail_price": {"type": "percentage", "value": 1.2, "formula": None}
            },
            "date_format": "%Y-%m-%d",
            "skip_rows": 0,
            "max_errors": 100,
        }

        return template
