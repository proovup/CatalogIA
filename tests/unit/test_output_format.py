import pytest
from ecoia.services.output_format_service import OutputFormatService
from ecoia.schemas.output_format import OutputFormatConfig


@pytest.fixture
def sample_yaml():
    return """
format_version: "1.0"
target_entity: "product"
fields:
  - name: "product_name"
    type: "string"
    transform: ["trim", "capitalize"]
    required: true
  - name: "price"
    type: "float"
    default: 0.0
  - name: "reference"
    type: "string"
    transform: ["uppercase"]
  - name: "slug"
    type: "string"
    transform: ["slugify"]
  - name: "margin"
    type: "float"
    calculation: "price * 0.2"
  - name: "is_active"
    type: "boolean"
    const: true
    default: true
"""


def test_load_config(sample_yaml):
    service = OutputFormatService()
    config = service.load_config(sample_yaml)
    assert isinstance(config, OutputFormatConfig)
    assert config.target_entity == "product"
    assert len(config.fields) == 6


def test_generate_system_prompt(sample_yaml):
    service = OutputFormatService()
    config = service.load_config(sample_yaml)
    prompt = service.generate_system_prompt(config)
    assert "product" in prompt
    assert "product_name" in prompt
    assert "JSON" in prompt


def test_apply_transformations(sample_yaml):
    service = OutputFormatService()
    config = service.load_config(sample_yaml)

    raw_data = {
        "product_name": "  ma super chaise  ",
        "price": 100.0,
        "reference": "ref-123",
        "slug": "Ma Super Chaise",
    }

    processed = service.apply_transformations(raw_data, config)

    assert processed["product_name"] == "Ma super chaise"
    assert processed["reference"] == "REF-123"
    assert processed["slug"] == "ma-super-chaise"
    assert processed["margin"] == 20.0
    assert processed["is_active"] is True


def test_clean_html_transformation():
    service = OutputFormatService()
    yaml_config = """
format_version: "1.0"
target_entity: "test"
fields:
  - name: "description"
    type: "string"
    transform: ["clean_html_tags"]
"""
    config = service.load_config(yaml_config)
    data = {"description": "<p>Hello <b>World</b></p>"}
    processed = service.apply_transformations(data, config)
    assert processed["description"] == "Hello World"


def test_exclude_from_extraction():
    """Test that fields with exclude_from_extraction are not included in AI prompt"""
    service = OutputFormatService()
    yaml_config = """
format_version: "1.0"
target_entity: "product"
fields:
  - name: "product_name"
    type: "string"
    required: true
  - name: "internal_id"
    type: "string"
    default: "AUTO-001"
    exclude_from_extraction: true
  - name: "generated_field"
    type: "string"
    default: "Generated"
    exclude_from_extraction: true
  - name: "seo_title"
    type: "string"
    ai_instruction: "Générer un titre SEO optimisé"
    description: "Titre SEO généré par l'IA"
"""
    config = service.load_config(yaml_config)

    # Test that excluded fields are not in the prompt
    prompt = service.generate_system_prompt(config)
    assert "product_name" in prompt
    assert "internal_id" not in prompt
    assert "generated_field" not in prompt
    assert "seo_title" not in prompt  # Excluded because it has ai_instruction

    # Test that excluded fields get their default values
    data = {"product_name": "Test Product"}
    processed = service.apply_transformations(data, config)

    assert processed["product_name"] == "Test Product"
    assert processed["internal_id"] == "AUTO-001"
    assert processed["generated_field"] == "Generated"
    assert processed["seo_title"] is None  # No default value, so None
