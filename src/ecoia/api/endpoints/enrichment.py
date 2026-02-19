"""
Enrichment API endpoints — Upload documents to enrich existing products.
"""

import json
import threading
import uuid as uuid_mod
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select

from ecoia.db.database import get_db, SessionLocal
from ecoia.db.models import Document, EnrichmentDocument, Product
from ecoia.services.upload_service import FileUploadService
from ecoia.services.enrichment_service import EnrichmentService

import asyncio

# In-memory job store for enrichment progress
_enrichment_jobs: Dict[str, Dict[str, Any]] = {}

router = APIRouter(prefix="/enrichment", tags=["enrichment"])


# ---------- Schemas ----------


class EnrichmentProcessRequest(BaseModel):
    document_id: str
    product_ids: List[str]  # List of product UUIDs to enrich
    enrichment_type: str = "other"  # notice, catalogue, fiche_technique, other
    provider: Optional[str] = None
    model_name: Optional[str] = None


class EnrichmentDocumentOut(BaseModel):
    id: str
    document_id: str
    product_id: str
    product_name: Optional[str] = None
    document_filename: Optional[str] = None
    enrichment_type: str
    extracted_data: Optional[dict] = None
    status: str
    match_confidence: Optional[float] = None
    match_method: Optional[str] = None
    error_message: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


# ---------- Helpers ----------


def _enrichment_doc_to_out(
    ed: EnrichmentDocument,
    product_name: str = "",
    doc_filename: str = "",
) -> dict:
    return {
        "id": str(ed.id),
        "document_id": str(ed.document_id),
        "product_id": str(ed.product_id),
        "product_name": product_name,
        "document_filename": doc_filename,
        "enrichment_type": ed.enrichment_type,
        "extracted_data": ed.extracted_data,
        "status": ed.status,
        "match_confidence": ed.match_confidence,
        "match_method": ed.match_method,
        "error_message": ed.error_message,
        "created_at": ed.created_at.isoformat() if ed.created_at else None,
        "updated_at": ed.updated_at.isoformat() if ed.updated_at else None,
    }


# ---------- Endpoints ----------


@router.post("/upload")
async def upload_enrichment_document(
    file: UploadFile = File(...),
    enrichment_type: str = Form("other"),
    db: Session = Depends(get_db),
):
    """Upload a document for enrichment (same validation as regular upload)."""
    service = FileUploadService(db)
    doc = await service.save_file(file, supplier_id=None)

    # Tag the document as an enrichment source
    if not doc.meta_data:
        doc.meta_data = {}
    doc.meta_data["enrichment_type"] = enrichment_type
    doc.meta_data["is_enrichment"] = True
    db.commit()

    return {
        "id": str(doc.id),
        "filename": doc.filename,
        "file_type": doc.file_type,
        "file_size": doc.file_size,
        "status": doc.status,
        "enrichment_type": enrichment_type,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
    }


@router.post("/process")
async def process_enrichment(
    req: EnrichmentProcessRequest,
    db: Session = Depends(get_db),
):
    """Start enrichment as a background job. Returns job_id for progress tracking."""
    doc = db.get(Document, UUID(req.document_id))
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Validate product IDs
    product_uuids = [UUID(pid) for pid in req.product_ids]
    products = db.execute(select(Product).where(Product.id.in_(product_uuids))).scalars().all()

    if not products:
        raise HTTPException(status_code=404, detail="Aucun produit trouvé avec les IDs fournis")

    job_id = str(uuid_mod.uuid4())
    _enrichment_jobs[job_id] = {
        "status": "starting",
        "progress": 0,
        "total": 100,
        "message": "Démarrage de l'enrichissement...",
        "count": 0,
        "error": None,
        "done": False,
    }

    # Mark document as processing
    doc.status = "processing"
    db.commit()

    # Launch background thread
    thread = threading.Thread(
        target=_run_enrichment_job,
        args=(
            job_id,
            doc.id,
            [p.id for p in products],
            req.enrichment_type,
            req.provider,
            req.model_name,
        ),
        daemon=True,
    )
    thread.start()

    return {"job_id": job_id, "status": "started", "products_count": len(products)}


@router.get("/{job_id}/progress")
async def enrichment_progress(job_id: str):
    """SSE endpoint streaming enrichment progress."""
    if job_id not in _enrichment_jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_stream():
        while True:
            job = _enrichment_jobs.get(job_id)
            if not job:
                yield f"data: {json.dumps({'status': 'error', 'message': 'Job not found'})}\n\n"
                break

            yield f"data: {json.dumps(job)}\n\n"

            if job.get("done"):
                await asyncio.sleep(1)
                _enrichment_jobs.pop(job_id, None)
                break

            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/documents", response_model=List[EnrichmentDocumentOut])
async def list_enrichment_documents(
    product_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """List enrichment documents, optionally filtered by product."""
    service = EnrichmentService(db)
    pid = UUID(product_id) if product_id else None
    eds = service.list_enrichment_documents(product_id=pid)

    # Build caches
    doc_ids = {ed.document_id for ed in eds}
    prod_ids = {ed.product_id for ed in eds}

    doc_map = {}
    if doc_ids:
        docs = db.execute(select(Document).where(Document.id.in_(doc_ids))).scalars().all()
        doc_map = {d.id: d.filename for d in docs}

    prod_map = {}
    if prod_ids:
        prods = db.execute(select(Product).where(Product.id.in_(prod_ids))).scalars().all()
        prod_map = {p.id: p.name or "" for p in prods}

    return [
        _enrichment_doc_to_out(
            ed,
            product_name=prod_map.get(ed.product_id, ""),
            doc_filename=doc_map.get(ed.document_id, ""),
        )
        for ed in eds
    ]


@router.get("/documents/{enrichment_id}", response_model=EnrichmentDocumentOut)
async def get_enrichment_document(
    enrichment_id: UUID,
    db: Session = Depends(get_db),
):
    """Get details of an enrichment document."""
    service = EnrichmentService(db)
    ed = service.get_enrichment_document(enrichment_id)
    if not ed:
        raise HTTPException(status_code=404, detail="Enrichment document not found")

    doc = db.get(Document, ed.document_id)
    product = db.get(Product, ed.product_id)

    return _enrichment_doc_to_out(
        ed,
        product_name=product.name if product else "",
        doc_filename=doc.filename if doc else "",
    )


@router.delete("/documents/{enrichment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_enrichment_document(
    enrichment_id: UUID,
    db: Session = Depends(get_db),
):
    """Delete an enrichment document."""
    service = EnrichmentService(db)
    if not service.delete_enrichment_document(enrichment_id):
        raise HTTPException(status_code=404, detail="Enrichment document not found")


@router.get("/product/{product_id}", response_model=List[EnrichmentDocumentOut])
async def get_product_enrichments(
    product_id: UUID,
    db: Session = Depends(get_db),
):
    """Get all enrichment documents linked to a specific product."""
    service = EnrichmentService(db)
    eds = service.list_enrichment_documents(product_id=product_id)

    doc_ids = {ed.document_id for ed in eds}
    doc_map = {}
    if doc_ids:
        docs = db.execute(select(Document).where(Document.id.in_(doc_ids))).scalars().all()
        doc_map = {d.id: d.filename for d in docs}

    product = db.get(Product, product_id)
    pname = product.name if product else ""

    return [_enrichment_doc_to_out(ed, product_name=pname, doc_filename=doc_map.get(ed.document_id, "")) for ed in eds]


# ---------- Background job ----------


def _run_enrichment_job(
    job_id: str,
    document_id: UUID,
    product_ids: List[UUID],
    enrichment_type: str,
    provider: Optional[str],
    model_name: Optional[str],
):
    """Background enrichment running in a separate thread with its own DB session."""
    import time as _time

    db = SessionLocal()
    t0 = _time.monotonic()

    def _elapsed():
        return round(_time.monotonic() - t0, 1)

    try:
        job = _enrichment_jobs[job_id]

        def on_progress(current, total, msg, count):
            job["progress"] = current
            job["total"] = total
            job["message"] = f"[{_elapsed()}s] {msg}"
            job["count"] = count

        job["status"] = "processing"
        job["message"] = f"[{_elapsed()}s] Démarrage du pipeline d'enrichissement..."

        service = EnrichmentService(db)
        results = service.run_enrichment(
            document_id=document_id,
            product_ids=product_ids,
            enrichment_type=enrichment_type,
            provider=provider,
            model_name=model_name,
            on_progress=on_progress,
        )

        job["status"] = "done"
        job["message"] = f"Terminé en {_elapsed()}s : {len(results)} produit(s) enrichi(s)"
        job["count"] = len(results)
        job["done"] = True

    except Exception as e:
        import traceback

        traceback.print_exc()
        job = _enrichment_jobs.get(job_id, {})
        job["status"] = "error"
        job["error"] = str(e)
        job["done"] = True

        doc = db.get(Document, document_id)
        if doc:
            doc.status = "failed"
            doc.error_message = str(e)
            db.commit()
    finally:
        db.close()
