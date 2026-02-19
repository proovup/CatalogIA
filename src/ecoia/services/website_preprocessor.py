from __future__ import annotations

import json
import re
from collections import deque
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from ecoia.core.llm_factory import LLMFactory


_TIMEOUT = 15.0


def preprocess_website(
    *,
    start_url: str,
    crawl_mode: str = "manual",
    urls: Optional[List[str]] = None,
    max_pages: int = 30,
    max_depth: int = 2,
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
):
    from ecoia.services.source_preprocessor_service import InMemoryTabularParser, PreprocessResult

    start = _normalize_url(start_url)
    if not start:
        raise ValueError("URL de départ invalide")

    max_pages = max(1, min(int(max_pages or 30), 200))
    max_depth = max(0, min(int(max_depth or 2), 5))
    domain = urlparse(start).netloc.lower()

    candidate_urls = _collect_urls(
        start_url=start,
        crawl_mode=crawl_mode,
        urls=urls or [],
        max_pages=max_pages,
        max_depth=max_depth,
        domain=domain,
    )

    if not candidate_urls:
        raise ValueError("Aucune URL exploitable trouvée pour l'extraction website")

    header = ["name", "description", "price", "reference", "brand", "category", "source_url"]
    rows: List[List[Any]] = []

    for url in candidate_urls:
        html = _fetch_url(url)
        if not html:
            continue
        item = _extract_product_from_html(url=url, html=html, provider=provider, model_name=model_name)
        if not item.get("name"):
            continue
        rows.append(
            [
                item.get("name"),
                item.get("description"),
                item.get("price"),
                item.get("reference"),
                item.get("brand"),
                item.get("category"),
                url,
            ]
        )

    if not rows:
        raise ValueError("Aucune fiche produit exploitable trouvée sur le périmètre website")

    parser = InMemoryTabularParser(
        {"master": [header, *rows]},
        metadata={
            "source": "website",
            "start_url": start,
            "crawl_mode": crawl_mode,
            "domain": domain,
            "total_urls": len(candidate_urls),
        },
    )
    parsed = parser.parse(start)
    return PreprocessResult(parser=parser, parsed=parsed, metadata=parsed.get("metadata", {}))


def _collect_urls(
    *,
    start_url: str,
    crawl_mode: str,
    urls: List[str],
    max_pages: int,
    max_depth: int,
    domain: str,
) -> List[str]:
    mode = (crawl_mode or "manual").lower()

    if mode == "manual":
        raw_urls = urls or [start_url]
        normalized = [_normalize_url(u) for u in raw_urls]
        filtered = [u for u in normalized if u and _is_same_domain(u, domain)]
        return list(dict.fromkeys(filtered))[:max_pages]

    discovered: List[str] = []
    visited: Set[str] = set()
    queue: deque[Tuple[str, int]] = deque([(start_url, 0)])
    effective_depth = max_depth if mode == "auto" else min(max_depth, 2)

    while queue and len(discovered) < max_pages:
        current, depth = queue.popleft()
        if current in visited:
            continue
        visited.add(current)

        html = _fetch_url(current)
        if not html:
            continue

        if _looks_like_product_page(current, html):
            discovered.append(current)

        if depth >= effective_depth:
            continue

        for link in _extract_links(current, html):
            if link in visited:
                continue
            if not _is_same_domain(link, domain):
                continue
            queue.append((link, depth + 1))

    if not discovered and _is_same_domain(start_url, domain):
        discovered.append(start_url)

    return discovered[:max_pages]


def _fetch_url(url: str) -> Optional[str]:
    try:
        with httpx.Client(timeout=_TIMEOUT, follow_redirects=True) as client:
            resp = client.get(url)
            resp.raise_for_status()
            return resp.text
    except Exception:
        return None


def _extract_links(base_url: str, html: str) -> List[str]:
    soup = BeautifulSoup(html, "lxml")
    links: List[str] = []
    for a in soup.select("a[href]"):
        href = a.get("href", "").strip()
        if not href or href.startswith("#"):
            continue
        full = urljoin(base_url, href)
        parsed = urlparse(full)
        if parsed.scheme not in ("http", "https"):
            continue
        links.append(f"{parsed.scheme}://{parsed.netloc}{parsed.path}" + (f"?{parsed.query}" if parsed.query else ""))
    return list(dict.fromkeys(links))


def _extract_product_from_html(
    *,
    url: str,
    html: str,
    provider: Optional[str],
    model_name: Optional[str],
) -> Dict[str, Any]:
    soup = BeautifulSoup(html, "lxml")
    json_ld = _extract_jsonld_product(soup)

    name = (json_ld.get("name") if json_ld else None) or _extract_title(soup)
    description = (json_ld.get("description") if json_ld else None) or _extract_description(soup)
    brand = _extract_brand(soup, json_ld)
    price = _extract_price(soup, json_ld)
    reference = _extract_reference(soup, json_ld)
    category = _extract_category(soup, json_ld)

    if not name and provider:
        guessed = _llm_extract_single_product(html[:50000], provider=provider, model_name=model_name)
        name = guessed.get("name") or name
        description = description or guessed.get("description")
        price = price or guessed.get("price")
        reference = reference or guessed.get("reference")
        brand = brand or guessed.get("brand")
        category = category or guessed.get("category")

    return {
        "name": name,
        "description": description,
        "price": price,
        "reference": reference,
        "brand": brand,
        "category": category,
        "source_url": url,
    }


def _llm_extract_single_product(
    html_snippet: str, *, provider: Optional[str], model_name: Optional[str]
) -> Dict[str, Any]:
    try:
        llm = LLMFactory.get_llm(provider=provider, model_name=model_name, temperature=0)
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """Extrait une fiche produit depuis du HTML. Retourne UNIQUEMENT ce JSON:
{"name": "", "description": "", "price": "", "reference": "", "brand": "", "category": ""}
Si inconnu: chaîne vide.""",
                ),
                ("human", "HTML:\n{html}"),
            ]
        )
        chain = prompt | llm | StrOutputParser()
        response = chain.invoke({"html": html_snippet})
        match = re.search(r"\{.*\}", response, re.DOTALL)
        if match:
            parsed = json.loads(match.group())
            if isinstance(parsed, dict):
                return {k: parsed.get(k) for k in ["name", "description", "price", "reference", "brand", "category"]}
    except Exception:
        pass
    return {}


def _extract_jsonld_product(soup: BeautifulSoup) -> Dict[str, Any]:
    for tag in soup.find_all("script", type="application/ld+json"):
        raw = tag.string or tag.get_text(strip=True) or ""
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except Exception:
            continue
        candidates = payload if isinstance(payload, list) else [payload]
        for item in candidates:
            if not isinstance(item, dict):
                continue
            t = item.get("@type")
            if t == "Product" or (isinstance(t, list) and "Product" in t):
                return item
    return {}


def _extract_title(soup: BeautifulSoup) -> Optional[str]:
    for sel in ["h1", "[data-testid='product-title']", ".product-title", "#productTitle"]:
        node = soup.select_one(sel)
        if node and node.get_text(strip=True):
            return node.get_text(strip=True)
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    return None


def _extract_description(soup: BeautifulSoup) -> Optional[str]:
    for sel in ["meta[name='description']", ".product-description", "#productDescription", "[itemprop='description']"]:
        node = soup.select_one(sel)
        if not node:
            continue
        if node.name == "meta":
            content = node.get("content", "").strip()
            if content:
                return content
        txt = node.get_text(" ", strip=True)
        if txt:
            return txt
    return None


def _extract_brand(soup: BeautifulSoup, json_ld: Dict[str, Any]) -> Optional[str]:
    if json_ld:
        brand = json_ld.get("brand")
        if isinstance(brand, dict):
            name = brand.get("name")
            if name:
                return str(name)
        if isinstance(brand, str):
            return brand
    for sel in ["[itemprop='brand']", ".brand", ".product-brand"]:
        node = soup.select_one(sel)
        if node and node.get_text(strip=True):
            return node.get_text(strip=True)
    return None


def _extract_price(soup: BeautifulSoup, json_ld: Dict[str, Any]) -> Optional[str]:
    if json_ld:
        offers = json_ld.get("offers")
        if isinstance(offers, dict) and offers.get("price") is not None:
            return str(offers.get("price"))
        if isinstance(offers, list):
            for item in offers:
                if isinstance(item, dict) and item.get("price") is not None:
                    return str(item.get("price"))
    text = soup.get_text(" ", strip=True)
    match = re.search(r"(\d+[\.,]\d{1,2})\s?(€|eur|usd|\$)", text, re.IGNORECASE)
    if match:
        return match.group(1)
    return None


def _extract_reference(soup: BeautifulSoup, json_ld: Dict[str, Any]) -> Optional[str]:
    for key in ("sku", "gtin", "mpn", "productID"):
        if json_ld and json_ld.get(key):
            return str(json_ld.get(key))
    text = soup.get_text(" ", strip=True)
    match = re.search(r"\b(SKU|REF|EAN|GTIN)[:#\s-]*([A-Za-z0-9\-_/]{4,})", text, re.IGNORECASE)
    if match:
        return match.group(2)
    return None


def _extract_category(soup: BeautifulSoup, json_ld: Dict[str, Any]) -> Optional[str]:
    if json_ld and json_ld.get("category"):
        return str(json_ld.get("category"))
    breadcrumb = soup.select("nav.breadcrumb a, .breadcrumb a")
    if breadcrumb:
        labels = [x.get_text(strip=True) for x in breadcrumb if x.get_text(strip=True)]
        if labels:
            return " > ".join(labels[-3:])
    return None


def _looks_like_product_page(url: str, html: str) -> bool:
    low_url = url.lower()
    if any(token in low_url for token in ("/product", "/produit", "sku", "item")):
        return True
    soup = BeautifulSoup(html, "lxml")
    if _extract_jsonld_product(soup):
        return True
    if soup.select_one("[itemtype*='Product']"):
        return True
    has_h1 = bool(soup.select_one("h1"))
    has_price_hint = bool(re.search(r"\d+[\.,]\d{1,2}\s?(€|eur|usd|\$)", soup.get_text(" ", strip=True), re.IGNORECASE))
    return has_h1 and has_price_hint


def _normalize_url(raw: str) -> Optional[str]:
    if not raw:
        return None
    parsed = urlparse(raw.strip())
    if parsed.scheme not in ("http", "https"):
        return None
    if not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}" + (f"?{parsed.query}" if parsed.query else "")


def _is_same_domain(url: str, domain: str) -> bool:
    return urlparse(url).netloc.lower() == domain.lower()
