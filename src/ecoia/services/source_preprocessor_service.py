from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence


@dataclass
class PreprocessResult:
    parser: "InMemoryTabularParser"
    parsed: Dict[str, Any]
    metadata: Dict[str, Any]


class InMemoryTabularParser:
    """Expose in-memory rows as a parser compatible with extraction pipeline."""

    SAMPLE_SIZE = 5

    def __init__(self, sheets_rows: Dict[str, List[Sequence[Any]]], metadata: Optional[Dict[str, Any]] = None):
        self._sheets_rows = sheets_rows
        self._parsed_cache: Optional[Dict[str, Any]] = None
        self._metadata = metadata or {}

    def parse(self, file_path: str) -> Dict[str, Any]:
        if self._parsed_cache is not None:
            return self._parsed_cache

        sheets: Dict[str, Dict[str, Any]] = {}
        for sheet_name, rows in self._sheets_rows.items():
            if not rows or len(rows) < 2:
                continue
            header = list(rows[0])
            samples = [list(r) for r in rows[1 : self.SAMPLE_SIZE + 1]]
            sheets[sheet_name] = {
                "columns": header,
                "samples": samples,
                "total_rows": len(rows),
            }

        parsed = {
            "type": "tabular_doc",
            "sheets": sheets,
            "metadata": {"source": "in_memory", **self._metadata, "file_path": file_path},
        }
        self._parsed_cache = parsed
        return parsed

    def get_all_rows(self, file_path: str, sheet_name: str, max_rows: Optional[int] = None):
        rows = self._sheets_rows.get(sheet_name, [])
        if max_rows is not None:
            return rows[: max_rows + 1]
        return rows

    def close(self):
        self._sheets_rows = {}
        self._parsed_cache = None


class SourcePreprocessorService:
    def preprocess_presented_catalog(
        self,
        *,
        file_path: str,
        mode: str = "docling_ocr",
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> PreprocessResult:
        if mode == "docling_ocr":
            from ecoia.services.catalog_preprocessor import preprocess_docling

            return preprocess_docling(file_path=file_path)
        if mode == "vision_model":
            return self._preprocess_vision(file_path=file_path, provider=provider, model_name=model_name)
        raise ValueError(f"Mode catalogue présenté non supporté: {mode}")

    def _preprocess_vision(
        self,
        *,
        file_path: str,
        provider: Optional[str],
        model_name: Optional[str],
    ) -> PreprocessResult:
        from ecoia.services.catalog_preprocessor import (
            _extract_text_mistral_ocr,
            _rows_from_images,
        )

        effective_provider = provider or "mistral"
        content = ""

        if effective_provider == "mistral":
            content = _extract_text_mistral_ocr(file_path)

        if not content.strip():
            content = self._extract_text_best_effort(file_path)

        if content.strip():
            table_rows = self._rows_from_unstructured_text_with_llm(
                text=content,
                provider=effective_provider,
                model_name=model_name or "mistral-large-latest",
            )
        else:
            table_rows = _rows_from_images(
                file_path=file_path,
                provider=effective_provider,
                model_name=model_name or "mistral-large-latest",
            )

        if len(table_rows) < 2:
            raise ValueError("Le modèle Vision n'a pas pu reconstruire une table exploitable (OCR ou Vision)")

        parser = InMemoryTabularParser(
            {"master": table_rows},
            metadata={"source": "presented_catalog", "mode": "vision_model"},
        )
        parsed = parser.parse(file_path)
        return PreprocessResult(parser=parser, parsed=parsed, metadata=parsed.get("metadata", {}))

    def _extract_text_best_effort(self, file_path: str) -> str:
        from ecoia.parsers import ParserFactory

        parser = ParserFactory.get_parser(file_path)
        parsed = parser.parse(file_path)
        text = parsed.get("text") or parsed.get("content")
        if isinstance(text, list):
            lines = []
            for item in text:
                if isinstance(item, (list, tuple)):
                    lines.append(" | ".join(str(c) if c is not None else "" for c in item))
                else:
                    lines.append(str(item))
            text = "\n".join(lines)
        if text and isinstance(text, str) and text.strip():
            return text
        return ""

    def _rows_from_unstructured_text_with_llm(
        self,
        *,
        text: str,
        provider: Optional[str],
        model_name: Optional[str],
    ):
        from ecoia.services.catalog_preprocessor import _rows_from_unstructured_text_with_llm

        return _rows_from_unstructured_text_with_llm(text=text, provider=provider, model_name=model_name)

    def preprocess_website(
        self,
        *,
        start_url: str,
        crawl_mode: str = "manual",
        urls: Optional[List[str]] = None,
        max_pages: int = 30,
        max_depth: int = 2,
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> PreprocessResult:
        from ecoia.services import website_preprocessor as _wp
        from urllib.parse import urlparse

        start = _wp._normalize_url(start_url)
        if not start:
            raise ValueError("URL de départ invalide")

        max_pages = max(1, min(int(max_pages or 30), 200))
        max_depth = max(0, min(int(max_depth or 2), 5))
        domain = urlparse(start).netloc.lower()

        candidate_urls = _wp._collect_urls(
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
        rows: List[Any] = []

        for url in candidate_urls:
            html = self._fetch_url(url)
            if not html:
                continue
            item = self._extract_product_from_html(url=url, html=html, provider=provider, model_name=model_name)
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

    def _fetch_url(self, url: str) -> Optional[str]:
        from ecoia.services.website_preprocessor import _fetch_url

        return _fetch_url(url)

    def _extract_product_from_html(self, *, url: str, html: str, provider=None, model_name=None) -> Dict[str, Any]:
        from ecoia.services.website_preprocessor import _extract_product_from_html

        return _extract_product_from_html(url=url, html=html, provider=provider, model_name=model_name)
