from unittest.mock import MagicMock

from ecoia.services.product_extractor_service import ProductExtractorService


def test_apply_format_defaults_top_level_and_nested():
    service = ProductExtractorService(MagicMock())

    mapped_fields = {"name": "Produit A"}
    processed_payload = {
        "name": "Produit A",
        "pricing": {"price": 12.5},
    }
    format_config = {
        "fields": [
            {"name": "name", "type": "string", "default": "Nom par defaut"},
            {
                "name": "pricing",
                "type": "object",
                "fields": [
                    {"name": "price", "type": "float"},
                    {"name": "id_tax_rules_group", "type": "integer", "default": 1},
                ],
            },
            {"name": "active", "type": "boolean", "default": True},
        ]
    }

    service._apply_format_defaults(mapped_fields, processed_payload, format_config)

    # existing extracted value keeps priority
    assert processed_payload["name"] == "Produit A"

    # nested default gets injected
    assert processed_payload["pricing"]["id_tax_rules_group"] == 1

    # top-level default gets injected and reflected in mapped_fields
    assert processed_payload["active"] is True
    assert mapped_fields["active"] is True


def test_extract_products_from_excel_applies_mapping_override_and_max_products_limit():
    db = MagicMock()
    service = ProductExtractorService(db)

    parser = MagicMock()
    parser.get_all_rows.return_value = [
        ["SKU", "Libelle", "Prix"],
        ["A-001", "Produit A", "10.5"],
        ["A-002", "Produit B", "12.0"],
        ["A-003", "Produit C", "13.0"],
    ]

    products = service.extract_products_from_excel(
        file_path="dummy.xlsx",
        sheet_name="Produits",
        column_mapping={"name": 1, "price": 2},
        document_id="00000000-0000-0000-0000-000000000001",
        parser=parser,
        cross_sheet_index={"shared_columns": set(), "value_index": {}, "sheet_headers": {}},
        field_mapping_override={"reference": "SKU"},
        max_products=2,
    )

    assert len(products) == 2
    assert products[0].reference == "A-001"
    assert products[1].reference == "A-002"


def test_extract_products_from_excel_ignores_metadata_or_excluded_linked_sheets():
    db = MagicMock()
    service = ProductExtractorService(db)

    parser = MagicMock()

    def _rows(file_path, sheet_name):
        if sheet_name == "master":
            return [["sku", "name"], ["A1", "Produit A"]]
        if sheet_name == "meta":
            return [["sku", "description"], ["A1", "Description meta"]]
        if sheet_name == "tech":
            return [["sku", "brand"], ["A1", "Brand X"]]
        return []

    parser.get_all_rows.side_effect = _rows

    cross_sheet_index = {
        "shared_columns": {"sku"},
        "value_index": {"sku::A1": {"master": [1], "meta": [1], "tech": [1]}},
        "sheet_headers": {
            "master": ["sku", "name"],
            "meta": ["sku", "description"],
            "tech": ["sku", "brand"],
        },
    }

    analysis = {
        "master_sheet": "master",
        "sheets": [
            {"name": "master", "role": "master", "relation": "master"},
            {"name": "meta", "role": "metadata", "relation": "1:1"},
            {"name": "tech", "role": "enrichment", "relation": "1:1", "excluded": True},
        ],
    }

    products = service.extract_products_from_excel(
        file_path="dummy.xlsx",
        sheet_name="master",
        column_mapping={"reference": 0, "name": 1},
        document_id="00000000-0000-0000-0000-000000000001",
        parser=parser,
        cross_sheet_index=cross_sheet_index,
        analysis=analysis,
    )

    assert len(products) == 1
    assert products[0].name == "Produit A"
    assert products[0].processed_data.get("linked_data") == {}


def test_extract_products_from_excel_persists_custom_mapped_fields_in_processed_data():
    db = MagicMock()
    service = ProductExtractorService(db)

    parser = MagicMock()
    parser.get_all_rows.return_value = [
        ["Nom", "Prix", "EAN", "TVA"],
        ["Produit A", "10.5", "1234567890123", "20"],
    ]

    products = service.extract_products_from_excel(
        file_path="dummy.xlsx",
        sheet_name="Produits",
        column_mapping={
            "name": 0,
            "price": 1,
            "identifiers.ean13": 2,
            "pricing.tax_rate": 3,
        },
        document_id="00000000-0000-0000-0000-000000000001",
        parser=parser,
        cross_sheet_index={"shared_columns": set(), "value_index": {}, "sheet_headers": {}},
    )

    assert len(products) == 1
    processed = products[0].processed_data
    assert processed["name"] == "Produit A"
    assert processed["identifiers"]["ean13"] == "1234567890123"
    assert processed["pricing"]["tax_rate"] == "20"


def test_extract_products_from_tables_supports_mapping_override_and_max_products():
    db = MagicMock()
    service = ProductExtractorService(db)

    service._extract_csv_tables = MagicMock(
        return_value=[
            [
                ["SKU", "Nom", "Prix"],
                ["A-001", "Produit A", "10.5"],
                ["A-002", "Produit B", "12.0"],
            ]
        ]
    )

    products = service.extract_products_from_tables(
        file_path="dummy.csv",
        document_id="00000000-0000-0000-0000-000000000001",
        field_mapping_override={"reference": "SKU"},
        max_products=1,
    )

    assert len(products) == 1
    assert products[0].name == "Produit A"
    assert products[0].reference == "A-001"
