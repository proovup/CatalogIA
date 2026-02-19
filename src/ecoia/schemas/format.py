from datetime import datetime
from uuid import UUID
from typing import Optional, List
from pydantic import BaseModel, Field


class FormatCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    yaml_content: dict = Field(..., description="Parsed YAML content as JSON")


class FormatUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    yaml_content: Optional[dict] = None


class FormatResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    yaml_content: dict
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class FormatListItem(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    field_count: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


class FormatList(BaseModel):
    formats: List[FormatListItem]
    total: int
