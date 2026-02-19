import io
import zipfile
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ecoia.db.database import get_db
from ecoia.db.models import ProductScrapeResult
from ecoia.services.product_scraper_service import ProductScraperService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/scraping", tags=["scraping"])


# ---------- Schemas ----------


class ScrapeRequest(BaseModel):
    urls: Optional[List[str]] = None
    search_query: Optional[str] = None
    sites: Optional[List[str]] = None
    max_results: int = 5


class ScrapeResultOut(BaseModel):
    id: str
    product_id: str
    source_url: str
    source_site: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    characteristics: Optional[Dict[str, Any]] = None
    images: Optional[List[str]] = None
    scraped_at: Optional[str] = None

    class Config:
        from_attributes = True


class GalleryImageOut(BaseModel):
    url: str
    source_url: str
    source_site: str
    scrape_result_id: Optional[str] = None


class DownloadRequest(BaseModel):
    image_urls: List[str]


# ---------- Helpers ----------


def _result_to_out(r: ProductScrapeResult) -> ScrapeResultOut:
    return ScrapeResultOut(
        id=str(r.id),
        product_id=str(r.product_id),
        source_url=r.source_url,
        source_site=r.source_site,
        title=r.title,
        description=r.description,
        characteristics=r.characteristics,
        images=r.images,
        scraped_at=r.scraped_at.isoformat() if r.scraped_at else None,
    )


# ---------- Endpoints ----------


@router.get("/proxy-image")
async def proxy_image(url: str = Query(...)):
    try:
        img_bytes, ct = ProductScraperService.proxy_image(url)
        return Response(content=img_bytes, media_type=ct)
    except Exception as e:
        logger.warning("proxy-image failed for %s: %s", url, e)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Cannot fetch image: {e}")


@router.post("/{product_id}/scrape", response_model=List[ScrapeResultOut])
async def scrape_product(
    product_id: UUID,
    body: ScrapeRequest,
    db: Session = Depends(get_db),
):
    service = ProductScraperService(db)
    try:
        results = service.scrape_product(
            product_id=product_id,
            urls=body.urls,
            search_query=body.search_query,
            sites=body.sites,
            max_results=body.max_results,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.exception("Scrape failed for product %s", product_id)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    return [_result_to_out(r) for r in results]


@router.get("/{product_id}/scrape-results", response_model=List[ScrapeResultOut])
async def list_scrape_results(
    product_id: UUID,
    db: Session = Depends(get_db),
):
    service = ProductScraperService(db)
    return [_result_to_out(r) for r in service.get_scrape_results(product_id)]


@router.get("/{product_id}/scrape-results/{result_id}", response_model=ScrapeResultOut)
async def get_scrape_result(
    product_id: UUID,
    result_id: UUID,
    db: Session = Depends(get_db),
):
    service = ProductScraperService(db)
    r = service.get_scrape_result(result_id)
    if not r or r.product_id != product_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scrape result not found")
    return _result_to_out(r)


@router.delete("/{product_id}/scrape-results/{result_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_scrape_result(
    product_id: UUID,
    result_id: UUID,
    db: Session = Depends(get_db),
):
    service = ProductScraperService(db)
    r = service.get_scrape_result(result_id)
    if not r or r.product_id != product_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scrape result not found")
    service.delete_scrape_result(result_id)


@router.get("/{product_id}/gallery", response_model=List[GalleryImageOut])
async def get_product_gallery(
    product_id: UUID,
    db: Session = Depends(get_db),
):
    service = ProductScraperService(db)
    return service.get_product_gallery(product_id)


@router.post("/{product_id}/gallery/download")
async def download_gallery_images(
    product_id: UUID,
    body: DownloadRequest,
    db: Session = Depends(get_db),
):
    if not body.image_urls:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No images selected")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, url in enumerate(body.image_urls):
            try:
                img_bytes, ct = ProductScraperService.proxy_image(url)
                ext = _ext_from_ct(ct)
                zf.writestr(f"image_{i + 1}{ext}", img_bytes)
            except Exception as e:
                logger.warning("Failed to download image %s: %s", url, e)

    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=product_{product_id}_images.zip"},
    )


def _ext_from_ct(content_type: str) -> str:
    ct = content_type.lower()
    if "png" in ct:
        return ".png"
    if "gif" in ct:
        return ".gif"
    if "webp" in ct:
        return ".webp"
    if "svg" in ct:
        return ".svg"
    return ".jpg"
