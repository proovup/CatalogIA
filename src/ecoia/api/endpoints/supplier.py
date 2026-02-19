from uuid import UUID
from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.orm import Session

from ecoia.db.database import get_db
from ecoia.services.supplier_service import SupplierService
from ecoia.schemas.supplier import (
    SupplierCreate,
    SupplierUpdate,
    SupplierResponse,
    SupplierList,
    ConfigTestRequest,
    ConfigTestResponse,
)

router = APIRouter(prefix="/suppliers", tags=["suppliers"])


def get_supplier_service(db: Session = Depends(get_db)) -> SupplierService:
    """Dependency to get supplier service"""
    return SupplierService(db)


@router.post("/", response_model=SupplierResponse, status_code=status.HTTP_201_CREATED)
async def create_supplier(
    supplier_data: SupplierCreate,
    service: SupplierService = Depends(get_supplier_service),
):
    """Create a new supplier"""
    return await service.create_supplier(supplier_data)


@router.get("/", response_model=SupplierList)
async def get_suppliers(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    active_only: bool = Query(False, description="Filter only active suppliers"),
    service: SupplierService = Depends(get_supplier_service),
):
    """Get all suppliers with pagination"""
    return await service.get_suppliers(skip=skip, limit=limit, active_only=active_only)


@router.get("/{supplier_id}", response_model=SupplierResponse)
async def get_supplier(supplier_id: UUID, service: SupplierService = Depends(get_supplier_service)):
    """Get a supplier by ID"""
    return await service.get_supplier(supplier_id)


@router.get("/by-name/{name}", response_model=SupplierResponse)
async def get_supplier_by_name(name: str, service: SupplierService = Depends(get_supplier_service)):
    """Get a supplier by name"""
    return await service.get_supplier_by_name(name)


@router.put("/{supplier_id}", response_model=SupplierResponse)
async def update_supplier(
    supplier_id: UUID,
    supplier_data: SupplierUpdate,
    service: SupplierService = Depends(get_supplier_service),
):
    """Update a supplier"""
    return await service.update_supplier(supplier_id, supplier_data)


@router.delete("/{supplier_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_supplier(supplier_id: UUID, service: SupplierService = Depends(get_supplier_service)):
    """Delete a supplier (soft delete if has documents)"""
    await service.delete_supplier(supplier_id)


@router.get("/{supplier_id}/documents")
async def get_supplier_documents(
    supplier_id: UUID,
    db: Session = Depends(get_db),
):
    """Get all documents for a supplier"""
    from sqlalchemy import select
    from ecoia.db.models import Document

    docs = (
        db.execute(select(Document).where(Document.supplier_id == supplier_id).order_by(Document.created_at.desc()))
        .scalars()
        .all()
    )
    return [
        {
            "id": str(d.id),
            "filename": d.filename,
            "file_type": d.file_type,
            "file_size": d.file_size,
            "status": d.status,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in docs
    ]


@router.post("/test-config", response_model=ConfigTestResponse)
async def test_supplier_config(
    test_request: ConfigTestRequest,
    service: SupplierService = Depends(get_supplier_service),
):
    """Test a supplier configuration with a sample file"""
    return await service.test_config(test_request)
