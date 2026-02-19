from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class ProductOut(BaseModel):
    id: str
    document_id: str
    supplier_id: Optional[str] = None
    supplier_name: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    category: Optional[str] = None
    reference: Optional[str] = None
    brand: Optional[str] = None
    status: Optional[str] = None
    raw_data: Optional[dict] = None
    processed_data: Optional[dict] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    document_filename: Optional[str] = None

    class Config:
        from_attributes = True


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    category: Optional[str] = None
    reference: Optional[str] = None
    brand: Optional[str] = None
    status: Optional[str] = None


class ExtractRequest(BaseModel):
    document_id: Optional[str] = None
    format_name: str = "default"
    max_rows_per_sheet: Optional[int] = None
    analysis: Optional[Dict[str, Any]] = None
    field_mapping_override: Optional[Dict[str, Any]] = None
    max_products: Optional[int] = None
    source_mode: str = "document"
    presented_mode: str = "docling_ocr"
    provider: Optional[str] = None
    model_name: Optional[str] = None


class WebsiteSourceRequest(BaseModel):
    start_url: str
    crawl_mode: str = "manual"
    urls: Optional[List[str]] = None
    max_pages: int = 30
    max_depth: int = 2


class WebsiteExtractRequest(BaseModel):
    supplier_id: Optional[str] = None
    format_name: str = "default"
    website: WebsiteSourceRequest
    max_products: Optional[int] = None
    provider: Optional[str] = None
    model_name: Optional[str] = None


class AnalyzeRequest(BaseModel):
    document_id: str
    provider: str = "mistral"
    model_name: Optional[str] = None


class ClassifyRequest(BaseModel):
    provider: str = "mistral"
    model_name: Optional[str] = None


class RegenerateRequest(BaseModel):
    format_name: str = "default"
    provider: str = "mistral"
    model_name: Optional[str] = None


class RegenerateFieldRequest(BaseModel):
    field_name: str
    field_type: str = "string"
    field_label: str = ""
    ai_hint: str = ""
    ai_instruction: str = ""
    provider: str = "mistral"
    model_name: Optional[str] = None


class FormatInfo(BaseModel):
    key: str
    name: str
    fields: list


class ProductStatsOut(BaseModel):
    suppliers: int
    documents: int
    products: int
    validated: int
