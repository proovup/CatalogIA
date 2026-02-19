from pathlib import Path
from typing import List, Optional
from uuid import UUID

import yaml
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ecoia.db.database import get_db
from ecoia.db.models import Document, Product, Supplier
from ecoia.api.endpoints.products.schemas import ProductOut, ProductStatsOut, ProductUpdate
from ecoia.api.endpoints.products.helpers import product_to_out

router = APIRouter()


@router.get("/", response_model=List[ProductOut])
async def list_products(
    status_filter: Optional[str] = Query(None),
    supplier_id: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = (
        select(Product, Document).join(Document, Product.document_id == Document.id).order_by(Product.created_at.desc())
    )
    if status_filter:
        query = query.where(Product.status == status_filter)
    if supplier_id:
        query = query.where(Product.supplier_id == UUID(supplier_id))
    if search:
        query = query.where(
            Product.name.ilike(f"%{search}%")
            | Product.description.ilike(f"%{search}%")
            | Product.reference.ilike(f"%{search}%")
        )
    query = query.offset(skip).limit(limit)
    rows = db.execute(query).all()

    sup_ids = {p.supplier_id for p, d in rows if p.supplier_id}
    sup_map = {}
    if sup_ids:
        sups = db.execute(select(Supplier).where(Supplier.id.in_(sup_ids))).scalars().all()
        sup_map = {s.id: s.name for s in sups}

    return [product_to_out(p, d.filename, sup_map.get(p.supplier_id, "")) for p, d in rows]


@router.get("/stats", response_model=ProductStatsOut)
async def get_product_stats(db: Session = Depends(get_db)):
    suppliers = db.execute(select(func.count()).select_from(Supplier)).scalar() or 0
    documents = db.execute(select(func.count()).select_from(Document)).scalar() or 0
    products = db.execute(select(func.count()).select_from(Product)).scalar() or 0
    validated = db.execute(select(func.count()).select_from(Product).where(Product.status == "validated")).scalar() or 0
    return {"suppliers": suppliers, "documents": documents, "products": products, "validated": validated}


@router.get("/documents")
async def list_documents(db: Session = Depends(get_db)):
    docs = db.execute(select(Document).order_by(Document.created_at.desc())).scalars().all()
    return [
        {
            "id": str(d.id),
            "filename": d.filename,
            "file_type": d.file_type,
            "status": d.status,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        }
        for d in docs
    ]


@router.get("/formats")
async def list_formats():
    formats_dir = Path(__file__).resolve().parents[5] / "configs" / "product_formats"
    result = []
    if formats_dir.exists():
        for f in sorted(formats_dir.glob("*.yaml")):
            try:
                with open(f) as fh:
                    cfg = yaml.safe_load(fh)
                fields = cfg.get("fields", {})
                if isinstance(fields, list):
                    field_names = [fd.get("name", "") for fd in fields if isinstance(fd, dict)]
                elif isinstance(fields, dict):
                    field_names = list(fields.keys())
                else:
                    field_names = []
                result.append(
                    {
                        "key": f.stem,
                        "name": cfg.get("name", cfg.get("description", f.stem)),
                        "fields": field_names,
                    }
                )
            except Exception:
                continue
    return result


@router.get("/{product_id}", response_model=ProductOut)
async def get_product(product_id: UUID, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    doc = db.get(Document, product.document_id)
    return product_to_out(product, doc.filename if doc else "")


@router.put("/{product_id}", response_model=ProductOut)
async def update_product(product_id: UUID, data: ProductUpdate, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
    db.commit()
    db.refresh(product)
    doc = db.get(Document, product.document_id)
    return product_to_out(product, doc.filename if doc else "")


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(product_id: UUID, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    db.delete(product)
    db.commit()
