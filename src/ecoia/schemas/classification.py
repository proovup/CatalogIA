from typing import List, Optional
from pydantic import BaseModel, Field


class CategoryNode(BaseModel):
    name: str = Field(..., min_length=1)
    children: List["CategoryNode"] = Field(default_factory=list)


CategoryNode.model_rebuild()


class ClassificationRequest(BaseModel):
    product_title: str = Field(..., min_length=1)
    product_description: Optional[str] = None
    categories: List[CategoryNode]
    confidence_threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    ai_output: Optional[dict] = None
    provider: Optional[str] = None
    model_name: Optional[str] = None


class ClassificationResult(BaseModel):
    category_path: List[str]
    confidence: float = Field(..., ge=0.0, le=1.0)


class ClassificationResponse(BaseModel):
    category_path: List[str]
    confidence: float
    needs_review: bool
    reason: Optional[str] = None
