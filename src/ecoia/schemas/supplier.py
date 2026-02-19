from datetime import datetime
from uuid import UUID
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator


class ColumnMapping(BaseModel):
    """Mapping configuration for a column"""

    source: str = Field(..., description="Column name in the source file")
    target: str = Field(..., description="Target field in canonical model")
    required: bool = Field(default=True, description="Whether this column is required")
    transform: Optional[str] = Field(
        default=None, description="Transformation rule to apply"
    )


class FileConfig(BaseModel):
    """File format configuration"""

    file_type: str = Field(..., description="File type (csv, xlsx, etc.)")
    delimiter: Optional[str] = Field(
        default=",", description="CSV delimiter if applicable"
    )
    encoding: str = Field(default="utf-8", description="File encoding")
    has_header: bool = Field(default=True, description="Whether the file has headers")
    sheet_name: Optional[str] = Field(
        default=None, description="Excel sheet name if applicable"
    )


class PriceRule(BaseModel):
    """Price transformation rule"""

    type: str = Field(..., description="Rule type: fixed, percentage, formula")
    value: Optional[float] = Field(default=None, description="Rule value")
    formula: Optional[str] = Field(default=None, description="Custom formula")


class SupplierConfig(BaseModel):
    """Supplier configuration schema"""

    file_config: FileConfig
    column_mappings: List[ColumnMapping]
    price_rules: Optional[Dict[str, PriceRule]] = Field(
        default=None, description="Price transformation rules"
    )
    date_format: str = Field(default="%Y-%m-%d", description="Date format")
    skip_rows: int = Field(default=0, description="Number of rows to skip")
    max_errors: int = Field(default=100, description="Maximum errors before stopping")

    @field_validator("column_mappings")
    @classmethod
    def validate_mappings(cls, v):
        if not v:
            raise ValueError("At least one column mapping is required")
        return v


class SupplierBase(BaseModel):
    """Base supplier schema"""

    name: str = Field(..., min_length=1, max_length=255, description="Supplier name")
    description: Optional[str] = Field(default=None, description="Supplier description")
    config: Optional[SupplierConfig] = Field(
        default=None, description="Supplier configuration"
    )
    is_active: str = Field(default="active", description="Supplier status")


class SupplierCreate(SupplierBase):
    """Schema for creating a supplier"""

    pass


class SupplierUpdate(BaseModel):
    """Schema for updating a supplier"""

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    config: Optional[SupplierConfig] = None
    is_active: Optional[str] = None


class SupplierResponse(SupplierBase):
    """Schema for supplier response"""

    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SupplierList(BaseModel):
    """Schema for supplier list response"""

    suppliers: List[SupplierResponse]
    total: int
    page: int
    size: int


class ConfigTestRequest(BaseModel):
    """Schema for testing supplier configuration"""

    config: SupplierConfig
    sample_file_path: str


class ConfigTestResponse(BaseModel):
    """Schema for configuration test results"""

    success: bool
    errors: List[str] = []
    warnings: List[str] = []
    sample_data: Optional[List[Dict[str, Any]]] = None
    mapped_columns: List[str] = []
