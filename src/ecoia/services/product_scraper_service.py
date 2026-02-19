import logging
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
from uuid import UUID

import httpx
from bs4 import BeautifulSoup
from ddgs import DDGS
from sqlalchemy.orm import Session

from ecoia.db.models import Product, ProductScrapeResult

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
}

_TIMEOUT = 15.0


class ProductScraperService:
    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def scrape_product(
        self,
        product_id: UUID,
        urls: Optional[List[str]] = None,
        search_query: Optional[str] = None,
        sites: Optional[List[str]] = None,
        max_results: int = 5,
    ) -> List[ProductScrapeResult]:
        product = self.db.query(Product).filter(Product.id == product_id).first()
        if not product:
            raise ValueError(f"Product {product_id} not found")

        target_urls: List[str] = []

        if urls:
            target_urls.extend(urls)

        if search_query or (not urls):
            query = search_query or self._build_search_query(product)
            found = self._search_web(query, sites=sites, max_results=max_results)
            target_urls.extend(found)

        results: List[ProductScrapeResult] = []
        for url in target_urls:
            try:
                result = self._scrape_url(product_id, url)
                if result:
                    results.append(result)
            except Exception as e:
                logger.warning("Failed to scrape %s: %s", url, e)

        if results:
            self.db.add_all(results)
            self.db.commit()
            for r in results:
                self.db.refresh(r)

        return results

    def get_scrape_results(self, product_id: UUID) -> List[ProductScrapeResult]:
        return (
            self.db.query(ProductScrapeResult)
            .filter(ProductScrapeResult.product_id == product_id)
            .order_by(ProductScrapeResult.scraped_at.desc())
            .all()
        )

    def get_scrape_result(self, result_id: UUID) -> Optional[ProductScrapeResult]:
        return self.db.query(ProductScrapeResult).filter(ProductScrapeResult.id == result_id).first()

    def delete_scrape_result(self, result_id: UUID) -> bool:
        result = self.get_scrape_result(result_id)
        if result:
            self.db.delete(result)
            self.db.commit()
            return True
        return False

    def get_product_gallery(self, product_id: UUID) -> List[Dict[str, Any]]:
        product = self.db.query(Product).filter(Product.id == product_id).first()
        images: List[Dict[str, Any]] = []
        seen: set[str] = set()

        # 1) Images from product raw_data / processed_data (supplier-provided)
        if product:
            supplier_imgs = self._extract_images_from_data(product.raw_data)
            supplier_imgs += self._extract_images_from_data(product.processed_data)
            for url in supplier_imgs:
                if url not in seen:
                    seen.add(url)
                    images.append(
                        {
                            "url": url,
                            "source_url": "",
                            "source_site": "fournisseur",
                            "scrape_result_id": None,
                        }
                    )

        # 2) Images from scrape results
        results = self.get_scrape_results(product_id)
        for r in results:
            if not r.images:
                continue
            for img_url in r.images:
                if img_url not in seen:
                    seen.add(img_url)
                    images.append(
                        {
                            "url": img_url,
                            "source_url": r.source_url,
                            "source_site": r.source_site or urlparse(r.source_url).netloc,
                            "scrape_result_id": str(r.id),
                        }
                    )
        return images

    @staticmethod
    def _extract_images_from_data(data: Any) -> List[str]:
        if not data or not isinstance(data, dict):
            return []
        urls: List[str] = []
        _IMG_KEYS = {
            "image",
            "images",
            "photo",
            "photos",
            "img",
            "img_url",
            "image_url",
            "picture",
            "pictures",
            "thumbnail",
            "thumbnails",
            "visual",
            "visuel",
            "visuels",
            "photo_url",
            "photo_produit",
            "image_produit",
            "lien_image",
            "url_image",
            "media",
            "medias",
        }
        _IMG_EXT = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp", ".tiff")

        def _collect(obj: Any, depth: int = 0) -> None:
            if depth > 5:
                return
            if isinstance(obj, str):
                s = obj.strip()
                if s.startswith(("http://", "https://")) and any(
                    s.lower().endswith(ext) or ext in s.lower() for ext in _IMG_EXT
                ):
                    urls.append(s)
            elif isinstance(obj, list):
                for item in obj:
                    _collect(item, depth + 1)
            elif isinstance(obj, dict):
                for k, v in obj.items():
                    kl = k.lower().strip()
                    if kl in _IMG_KEYS:
                        if isinstance(v, str) and v.strip().startswith(("http://", "https://")):
                            urls.append(v.strip())
                        elif isinstance(v, list):
                            for item in v:
                                if isinstance(item, str) and item.strip().startswith(("http://", "https://")):
                                    urls.append(item.strip())
                    else:
                        _collect(v, depth + 1)

        _collect(data)
        return urls

    # ------------------------------------------------------------------
    # Proxy — fetch external image bytes
    # ------------------------------------------------------------------

    @staticmethod
    def proxy_image(url: str) -> tuple[bytes, str]:
        from urllib.parse import urlparse as _urlparse

        parsed = _urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        headers = {
            **_HEADERS,
            "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
            "Referer": f"{origin}/",
            "Origin": origin,
        }
        with httpx.Client(
            headers=headers,
            timeout=_TIMEOUT,
            follow_redirects=True,
            verify=False,
        ) as client:
            resp = client.get(url)
            resp.raise_for_status()
            ct = resp.headers.get("content-type", "image/jpeg")
            return resp.content, ct

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_search_query(product: Product) -> str:
        parts = []
        if product.name:
            parts.append(product.name)
        if product.reference:
            parts.append(product.reference)
        if product.brand:
            parts.append(product.brand)
        return " ".join(parts) or "product"

    @staticmethod
    def _search_web(query: str, sites: Optional[List[str]] = None, max_results: int = 5) -> List[str]:
        if sites:
            site_filter = " OR ".join(f"site:{s}" for s in sites)
            query = f"({site_filter}) {query}"

        urls: List[str] = []
        try:
            with DDGS() as ddgs:
                for r in ddgs.text(query, max_results=max_results):
                    href = r.get("href") or r.get("link")
                    if href:
                        urls.append(href)
        except Exception as e:
            logger.warning("DuckDuckGo search failed: %s", e)
        return urls

    def _scrape_url(self, product_id: UUID, url: str) -> Optional[ProductScrapeResult]:
        with httpx.Client(headers=_HEADERS, timeout=_TIMEOUT, follow_redirects=True) as client:
            resp = client.get(url)
            resp.raise_for_status()
            html = resp.text

        soup = BeautifulSoup(html, "lxml")

        title = self._extract_title(soup)
        description = self._extract_description(soup)
        images = self._extract_images(soup, url)
        characteristics = self._extract_characteristics(soup)

        if not title and not images and not description:
            return None

        domain = urlparse(url).netloc.replace("www.", "")

        return ProductScrapeResult(
            product_id=product_id,
            source_url=url,
            source_site=domain,
            title=title,
            description=description,
            characteristics=characteristics or None,
            images=images or None,
            raw_content=html[:50000],
        )

    # ------------------------------------------------------------------
    # HTML extraction helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_title(soup: BeautifulSoup) -> Optional[str]:
        for sel in ["h1", "[data-testid='product-title']", ".product-title", ".product-name", "#productTitle"]:
            el = soup.select_one(sel)
            if el and el.get_text(strip=True):
                return el.get_text(strip=True)
        og = soup.find("meta", property="og:title")
        if og and og.get("content"):
            return og["content"]
        if soup.title and soup.title.string:
            return soup.title.string.strip()
        return None

    @staticmethod
    def _extract_description(soup: BeautifulSoup) -> Optional[str]:
        for sel in [
            "[data-testid='product-description']",
            ".product-description",
            "#productDescription",
            ".product-detail__description",
            "meta[name='description']",
        ]:
            el = soup.select_one(sel)
            if el:
                if el.name == "meta":
                    return el.get("content", "").strip() or None
                text = el.get_text(separator="\n", strip=True)
                if text:
                    return text
        og = soup.find("meta", property="og:description")
        if og and og.get("content"):
            return og["content"]
        return None

    @staticmethod
    def _extract_images(soup: BeautifulSoup, base_url: str) -> List[str]:
        seen = set()
        images: List[str] = []
        parsed = urlparse(base_url)
        base = f"{parsed.scheme}://{parsed.netloc}"

        og_img = soup.find("meta", property="og:image")
        if og_img and og_img.get("content"):
            images.append(og_img["content"])
            seen.add(og_img["content"])

        for img in soup.find_all("img"):
            src = img.get("data-src") or img.get("src") or ""
            if not src or src.startswith("data:"):
                continue
            if src.startswith("//"):
                src = f"{parsed.scheme}:{src}"
            elif src.startswith("/"):
                src = f"{base}{src}"

            if src in seen:
                continue

            # Filter out small icons/tracking pixels
            w = img.get("width", "")
            h = img.get("height", "")
            try:
                if (w and int(w) < 50) or (h and int(h) < 50):
                    continue
            except ValueError:
                pass

            # Skip common non-product patterns
            lower = src.lower()
            if any(skip in lower for skip in ["logo", "icon", "sprite", "pixel", "tracking", "badge", "flag"]):
                continue

            seen.add(src)
            images.append(src)

        return images[:30]

    @staticmethod
    def _extract_characteristics(soup: BeautifulSoup) -> Optional[Dict[str, str]]:
        chars: Dict[str, str] = {}

        # Try tables with spec/characteristic patterns
        for table in soup.find_all("table"):
            for row in table.find_all("tr"):
                cells = row.find_all(["th", "td"])
                if len(cells) >= 2:
                    key = cells[0].get_text(strip=True)
                    val = cells[1].get_text(strip=True)
                    if key and val and len(key) < 100:
                        chars[key] = val

        # Try definition lists
        for dl in soup.find_all("dl"):
            dts = dl.find_all("dt")
            dds = dl.find_all("dd")
            for dt, dd in zip(dts, dds):
                key = dt.get_text(strip=True)
                val = dd.get_text(strip=True)
                if key and val:
                    chars[key] = val

        return chars if chars else None
