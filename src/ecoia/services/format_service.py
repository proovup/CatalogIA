from sqlalchemy.orm import Session
from sqlalchemy import select, func
from fastapi import HTTPException, status
from uuid import UUID

from ecoia.db.models import ProductFormat
from ecoia.schemas.format import (
    FormatCreate,
    FormatUpdate,
    FormatResponse,
    FormatList,
    FormatListItem,
)


class FormatService:

    def __init__(self, db: Session):
        self.db = db

    def _count_fields(self, yaml_content: dict) -> int:
        fields = yaml_content.get("fields", {})
        if isinstance(fields, list):
            return len(fields)
        elif isinstance(fields, dict):
            return len(fields)
        return 0

    async def create_format(self, data: FormatCreate) -> FormatResponse:
        db_format = ProductFormat(
            name=data.name,
            description=data.description,
            yaml_content=data.yaml_content,
        )
        self.db.add(db_format)
        self.db.commit()
        self.db.refresh(db_format)
        return FormatResponse.model_validate(db_format)

    async def get_format(self, format_id: UUID) -> FormatResponse:
        fmt = self.db.get(ProductFormat, format_id)
        if not fmt:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Format not found")
        return FormatResponse.model_validate(fmt)

    async def list_formats(self) -> FormatList:
        total = self.db.execute(select(func.count()).select_from(ProductFormat)).scalar() or 0
        rows = self.db.execute(select(ProductFormat).order_by(ProductFormat.created_at.desc())).scalars().all()

        items = []
        for r in rows:
            items.append(
                FormatListItem(
                    id=r.id,
                    name=r.name,
                    description=r.description,
                    field_count=self._count_fields(r.yaml_content),
                    created_at=r.created_at,
                )
            )
        return FormatList(formats=items, total=total)

    async def update_format(self, format_id: UUID, data: FormatUpdate) -> FormatResponse:
        fmt = self.db.get(ProductFormat, format_id)
        if not fmt:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Format not found")

        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(fmt, field, value)

        self.db.commit()
        self.db.refresh(fmt)
        return FormatResponse.model_validate(fmt)

    async def delete_format(self, format_id: UUID) -> None:
        fmt = self.db.get(ProductFormat, format_id)
        if not fmt:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Format not found")
        self.db.delete(fmt)
        self.db.commit()
