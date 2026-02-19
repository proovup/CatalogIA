import asyncio
import json
import threading
import uuid as uuid_mod
from datetime import datetime
from urllib.parse import urlparse
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ecoia.db.database import get_db
from ecoia.db.models import Document
from ecoia.api.endpoints.products.schemas import ExtractRequest, WebsiteExtractRequest
from ecoia.api.endpoints.products.extraction_jobs import (
    _extraction_jobs,
    run_extraction_job,
    run_website_extraction_job,
)

router = APIRouter()


@router.post("/extract")
async def extract_products(req: ExtractRequest, db: Session = Depends(get_db)):
    if req.source_mode == "website":
        raise HTTPException(
            status_code=400,
            detail="Le mode website doit utiliser l'endpoint /products/extract/website",
        )
    if req.source_mode not in ("document", "presented_catalog"):
        raise HTTPException(status_code=400, detail=f"source_mode non supporté: {req.source_mode}")
    if not req.document_id:
        raise HTTPException(status_code=400, detail="document_id est requis pour ce mode d'extraction")

    doc = db.get(Document, UUID(req.document_id))
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if not doc.file_path or not __import__("os").path.exists(doc.file_path):
        raise HTTPException(status_code=404, detail="Document file not found on disk")

    job_id = str(uuid_mod.uuid4())
    doc_id = doc.id
    file_path = doc.file_path
    filename = doc.filename
    supplier_id = doc.supplier_id

    doc.status = "processing"
    doc.error_message = None
    db.commit()

    _extraction_jobs[job_id] = {
        "status": "starting",
        "progress": 0,
        "total": 0,
        "message": "Démarrage de l'extraction...",
        "count": 0,
        "error": None,
        "done": False,
    }

    thread = threading.Thread(
        target=run_extraction_job,
        args=(
            job_id,
            doc_id,
            file_path,
            filename,
            supplier_id,
            req.format_name,
            req.analysis,
            req.field_mapping_override,
            req.max_products,
            req.source_mode,
            req.presented_mode,
            req.provider,
            req.model_name,
        ),
        daemon=True,
    )
    thread.start()

    return {"job_id": job_id, "status": "started"}


@router.post("/extract/website")
async def extract_products_from_website(req: WebsiteExtractRequest, db: Session = Depends(get_db)):
    supplier_uuid = UUID(req.supplier_id) if req.supplier_id else None
    domain = (urlparse(req.website.start_url).netloc or "website").replace("www.", "")

    doc = Document(
        id=uuid_mod.uuid4(),
        supplier_id=supplier_uuid,
        filename=f"website_{domain}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.html",
        file_type=".website",
        file_size=0,
        mime_type="text/html",
        upload_status="completed",
        upload_progress=100,
        file_path=None,
        status="processing",
        meta_data={"source_mode": "website", "website": req.website.model_dump()},
        error_message=None,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    job_id = str(uuid_mod.uuid4())
    _extraction_jobs[job_id] = {
        "status": "starting",
        "progress": 0,
        "total": 0,
        "message": "Démarrage de l'extraction website...",
        "count": 0,
        "error": None,
        "done": False,
    }

    thread = threading.Thread(
        target=run_website_extraction_job,
        args=(
            job_id,
            doc.id,
            supplier_uuid,
            req.format_name,
            req.website.model_dump(),
            req.max_products,
            req.provider,
            req.model_name,
        ),
        daemon=True,
    )
    thread.start()

    return {"job_id": job_id, "status": "started", "document_id": str(doc.id)}


@router.get("/extract/{job_id}/progress")
async def extraction_progress(job_id: str):
    if job_id not in _extraction_jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_stream():
        while True:
            job = _extraction_jobs.get(job_id)
            if not job:
                yield f"data: {json.dumps({'status': 'error', 'message': 'Job not found'})}\n\n"
                break
            yield f"data: {json.dumps(job)}\n\n"
            if job.get("done"):
                await asyncio.sleep(1)
                _extraction_jobs.pop(job_id, None)
                break
            await asyncio.sleep(0.3)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
