from sqlalchemy.orm import Session
from sqlalchemy import select, update, delete
from fastapi import HTTPException, status
from uuid import UUID

from ecoia.db.models import Supplier
from ecoia.schemas.supplier import (
    SupplierCreate,
    SupplierUpdate,
    SupplierResponse,
    SupplierList,
    ConfigTestRequest,
    ConfigTestResponse,
)


class SupplierService:
    """Service for managing suppliers"""

    def __init__(self, db: Session):
        self.db = db

    async def create_supplier(self, supplier_data: SupplierCreate) -> SupplierResponse:
        """Create a new supplier"""
        # Check if supplier name already exists
        existing = self.db.execute(select(Supplier).where(Supplier.name == supplier_data.name)).scalar_one_or_none()

        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Supplier with name '{supplier_data.name}' already exists",
            )

        # Convert config to dict if provided
        config_dict = supplier_data.config.model_dump() if supplier_data.config else None

        db_supplier = Supplier(
            name=supplier_data.name,
            description=supplier_data.description,
            config=config_dict,
            is_active=supplier_data.is_active,
        )

        self.db.add(db_supplier)
        self.db.commit()
        self.db.refresh(db_supplier)

        return SupplierResponse.model_validate(db_supplier)

    async def get_supplier(self, supplier_id: UUID) -> SupplierResponse:
        """Get a supplier by ID"""
        supplier = self.db.execute(select(Supplier).where(Supplier.id == supplier_id)).scalar_one_or_none()

        if not supplier:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")

        return SupplierResponse.model_validate(supplier)

    async def get_supplier_by_name(self, name: str) -> SupplierResponse:
        """Get a supplier by name"""
        supplier = self.db.execute(select(Supplier).where(Supplier.name == name)).scalar_one_or_none()

        if not supplier:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Supplier with name '{name}' not found",
            )

        return SupplierResponse.model_validate(supplier)

    async def get_suppliers(self, skip: int = 0, limit: int = 100, active_only: bool = False) -> SupplierList:
        """Get all suppliers with pagination"""
        query = select(Supplier)

        if active_only:
            query = query.where(Supplier.is_active == "active")

        from sqlalchemy import func

        # Get total count
        total_query = select(func.count()).select_from(Supplier)
        if active_only:
            total_query = total_query.where(Supplier.is_active == "active")
        total = self.db.execute(total_query).scalar() or 0

        # Get paginated results
        suppliers = (
            self.db.execute(query.offset(skip).limit(limit).order_by(Supplier.created_at.desc())).scalars().all()
        )

        return SupplierList(
            suppliers=[SupplierResponse.model_validate(s) for s in suppliers],
            total=total,
            page=skip // limit + 1,
            size=limit,
        )

    async def update_supplier(self, supplier_id: UUID, supplier_data: SupplierUpdate) -> SupplierResponse:
        """Update a supplier"""
        # Check if supplier exists
        supplier = self.db.execute(select(Supplier).where(Supplier.id == supplier_id)).scalar_one_or_none()

        if not supplier:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")

        # Check if new name conflicts with existing supplier
        if supplier_data.name and supplier_data.name != supplier.name:
            existing = self.db.execute(
                select(Supplier).where((Supplier.name == supplier_data.name) & (Supplier.id != supplier_id))
            ).scalar_one_or_none()

            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Supplier with name '{supplier_data.name}' already exists",
                )

        # Update fields
        update_data = supplier_data.model_dump(exclude_unset=True)
        if "config" in update_data and update_data["config"] is not None:
            update_data["config"] = update_data["config"].model_dump()

        self.db.execute(update(Supplier).where(Supplier.id == supplier_id).values(**update_data))

        self.db.commit()
        self.db.refresh(supplier)

        return SupplierResponse.model_validate(supplier)

    async def delete_supplier(self, supplier_id: UUID) -> bool:
        """Delete a supplier"""
        supplier = self.db.execute(select(Supplier).where(Supplier.id == supplier_id)).scalar_one_or_none()

        if not supplier:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found")

        # Check if supplier has associated documents
        from ecoia.db.models import Document

        doc_count = self.db.execute(select(Document).where(Document.supplier_id == supplier_id)).scalar()

        if doc_count:
            # Soft delete by deactivating
            self.db.execute(update(Supplier).where(Supplier.id == supplier_id).values(is_active="inactive"))
        else:
            # Hard delete if no documents
            self.db.execute(delete(Supplier).where(Supplier.id == supplier_id))

        self.db.commit()
        return True

    async def test_config(self, test_request: ConfigTestRequest) -> ConfigTestResponse:
        """Test a supplier configuration with a sample file"""
        import pandas as pd
        import os

        errors = []
        warnings = []
        mapped_columns = []
        sample_data = None

        # Check if file exists
        if not os.path.exists(test_request.sample_file_path):
            return ConfigTestResponse(
                success=False,
                errors=[f"File not found: {test_request.sample_file_path}"],
            )

        try:
            # Read sample file based on configuration
            config = test_request.config

            if config.file_config.file_type.lower() == "csv":
                df = pd.read_csv(
                    test_request.sample_file_path,
                    delimiter=config.file_config.delimiter,
                    encoding=config.file_config.encoding,
                    header=0 if config.file_config.has_header else None,
                    skiprows=config.skip_rows,
                )
            elif config.file_config.file_type.lower() in ["xlsx", "xls"]:
                df = pd.read_excel(
                    test_request.sample_file_path,
                    sheet_name=config.file_config.sheet_name or 0,
                    header=0 if config.file_config.has_header else None,
                    skiprows=config.skip_rows,
                )
            else:
                errors.append(f"Unsupported file type: {config.file_config.file_type}")
                return ConfigTestResponse(success=False, errors=errors)

            # Check column mappings
            source_columns = df.columns.tolist()

            for mapping in config.column_mappings:
                if mapping.source not in source_columns:
                    errors.append(f"Column '{mapping.source}' not found in file")
                else:
                    mapped_columns.append(mapping.source)

            # Get sample data (first 5 rows)
            sample_data = df.head().to_dict(orient="records")

            # Validate required columns
            for mapping in config.column_mappings:
                if mapping.required and mapping.source in source_columns:
                    if df[mapping.source].isnull().all():
                        errors.append(f"Required column '{mapping.source}' is empty")

            # Warnings for unmapped columns
            unmapped = set(source_columns) - set(m.source for m in config.column_mappings)
            if unmapped:
                warnings.append(f"Unmapped columns: {', '.join(unmapped)}")

            return ConfigTestResponse(
                success=len(errors) == 0,
                errors=errors,
                warnings=warnings,
                sample_data=sample_data,
                mapped_columns=mapped_columns,
            )

        except Exception as e:
            return ConfigTestResponse(success=False, errors=[f"Error reading file: {str(e)}"])
