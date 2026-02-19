from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field


class FieldValidation(BaseModel):
    pattern: Optional[str] = None
    message: Optional[str] = None
    max_length: Optional[int] = None
    min_length: Optional[int] = None
    max_value: Optional[Union[int, float]] = None
    min_value: Optional[Union[int, float]] = None
    min: Optional[Union[int, float]] = None  # Alias for min_value in example


class OutputField(BaseModel):
    name: str
    type: str  # string, integer, float, boolean, date, html, enum, object, array
    description: Optional[str] = None
    required: bool = False
    default: Optional[Any] = None
    const: bool = False
    unit: Optional[str] = None
    ai_instruction: Optional[str] = None
    transform: List[str] = Field(default_factory=list)
    validation: Optional[FieldValidation] = None
    options: Optional[List[str]] = None  # For enum
    mapping: Optional[Dict[str, str]] = None  # For enum translation
    calculation: Optional[str] = None  # For calculated fields
    fields: Optional[List["OutputField"]] = None  # For nested objects
    item_type: Optional[str] = None  # For arrays
    exclude_from_extraction: bool = False  # If true, field is not extracted by AI


# Handle recursive models
OutputField.model_rebuild()


class GlobalProcessingOptions(BaseModel):
    clean_html: bool = True
    translate_to: Optional[str] = None
    currency: Optional[str] = "EUR"


class OutputFormatConfig(BaseModel):
    format_version: str
    target_entity: str
    description: Optional[str] = None
    processing: GlobalProcessingOptions = Field(default_factory=GlobalProcessingOptions)
    fields: List[OutputField]
