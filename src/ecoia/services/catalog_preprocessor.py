from __future__ import annotations

import base64
import json
import os
import re
from io import BytesIO
from typing import Any, List, Optional, Sequence

import httpx
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from ecoia.core.llm_factory import LLMFactory


def preprocess_docling(*, file_path: str):
    from ecoia.parsers.docling_tabular import DoclingTabularParser
    from ecoia.services.source_preprocessor_service import InMemoryTabularParser, PreprocessResult

    parser = DoclingTabularParser()
    parsed = parser.parse(file_path)
    rows_by_sheet = {}
    for sheet_name in parsed.get("sheets", {}).keys():
        rows = parser.get_all_rows(file_path, sheet_name)
        if rows and len(rows) >= 2:
            rows_by_sheet[sheet_name] = rows

    in_memory = InMemoryTabularParser(
        rows_by_sheet,
        metadata={"source": "presented_catalog", "mode": "docling_ocr"},
    )
    out = in_memory.parse(file_path)
    parser.close()
    return PreprocessResult(parser=in_memory, parsed=out, metadata=out.get("metadata", {}))


def preprocess_vision(
    *,
    file_path: str,
    provider: Optional[str],
    model_name: Optional[str],
):
    from ecoia.services.source_preprocessor_service import InMemoryTabularParser, PreprocessResult

    effective_provider = provider or "mistral"
    content = ""

    if effective_provider == "mistral":
        content = _extract_text_mistral_ocr(file_path)

    if content.strip():
        table_rows = _rows_from_unstructured_text_with_llm(
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


def _extract_text_mistral_ocr(file_path: str) -> str:
    from ecoia.config import settings

    if not settings.MISTRAL_API_KEY:
        return ""

    url = "https://api.mistral.ai/v1/ocr"
    headers = {"Authorization": f"Bearer {settings.MISTRAL_API_KEY}"}

    try:
        with open(file_path, "rb") as f:
            content = f.read()
        files = {"file": (os.path.basename(file_path), content)}
        data = {"model": "mistral-ocr-latest"}
        with httpx.Client(timeout=120.0) as client:
            resp = client.post(url, headers=headers, files=files, data=data)
            resp.raise_for_status()
            payload = resp.json()
            pages = payload.get("pages", [])
            return "\n\n".join(p.get("markdown", "") for p in pages)
    except Exception as e:
        print(f"Mistral OCR Error: {str(e)}")
        return ""


def _rows_from_images(*, file_path: str, provider: str, model_name: str) -> List[List[Any]]:
    images_base64 = []
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".pdf":
        try:
            import fitz
            from PIL import Image

            doc = fitz.open(file_path)
            for page_index in range(min(len(doc), 15)):
                page = doc[page_index]
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                buffered = BytesIO()
                img.save(buffered, format="JPEG", quality=85)
                images_base64.append(base64.b64encode(buffered.getvalue()).decode("utf-8"))
            doc.close()
        except Exception:
            return []
    elif ext in (".jpg", ".jpeg", ".png", ".webp"):
        with open(file_path, "rb") as f:
            images_base64.append(base64.b64encode(f.read()).decode("utf-8"))
    else:
        return []

    if not images_base64:
        return []

    return _rows_from_images_with_vision_llm(
        images_base64=images_base64,
        provider=provider,
        model_name=model_name,
    )


def _rows_from_images_with_vision_llm(
    *,
    images_base64: List[str],
    provider: str,
    model_name: str,
) -> List[List[Any]]:
    from langchain_core.messages import HumanMessage

    llm = LLMFactory.get_llm(provider=provider, model_name=model_name, temperature=0, max_tokens=4096)

    content = [
        {
            "type": "text",
            "text": """Tu es un expert en extraction visuelle de données. Analyse ces pages de catalogue et reconstruis un tableau JSON complet des produits.
Retourne UNIQUEMENT un JSON valide au format:
{
  "columns": ["name", "description", "price", "reference", "brand", "category"],
  "rows": [[...], [...]]
}
Règles strictes :
- Colonnes: name, description, price, reference, brand, category
- Name requis
- Si une information manque, laisse null
- Ne retourne RIEN d'autre que le JSON.""",
        }
    ]

    for img_b64 in images_base64[:10]:
        content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}})

    message = HumanMessage(content=content)

    try:
        response = llm.invoke([message])
        text_response = response.content if hasattr(response, "content") else str(response)
        match = re.search(r"\{.*\}", text_response, re.DOTALL)
        if match:
            payload = json.loads(match.group())
            columns = payload.get("columns") or []
            rows = payload.get("rows") or []
            return _normalize_table(columns, rows)
    except Exception as e:
        print(f"Vision LLM Error: {str(e)}")
        raise e

    return []


def _rows_from_unstructured_text_with_llm(
    *,
    text: str,
    provider: Optional[str],
    model_name: Optional[str],
) -> List[List[Any]]:
    context_text = text[:500000]

    llm = LLMFactory.get_llm(provider=provider, model_name=model_name, temperature=0)
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """Tu reconstruis un tableau de produits depuis du texte non structuré (catalogue avec texte/images OCR).
Retourne UNIQUEMENT un JSON valide au format:
{
  "columns": ["name", "description", "price", "reference", "brand", "category"],
  "rows": [[...], [...]]
}
Règles:
- Colonnes minimales: name, description, price, reference, brand, category
- Le champ name est obligatoire pour une ligne valide
- price doit rester texte si incertain
- Pas d'explication hors JSON""",
            ),
            ("human", "Texte catalogue:\n{text}"),
        ]
    )

    try:
        chain = prompt | llm | StrOutputParser()
        response = chain.invoke({"text": context_text})
        match = re.search(r"\{.*\}", response, re.DOTALL)
        if match:
            payload = json.loads(match.group())
            columns = payload.get("columns") or []
            rows = payload.get("rows") or []
            normalized = _normalize_table(columns, rows)
            if len(normalized) >= 2:
                return normalized
    except Exception:
        pass

    return _fallback_rows_from_text(text)


def _normalize_table(columns: Sequence[Any], rows: Sequence[Sequence[Any]]) -> List[List[Any]]:
    cols = [str(c).strip() if str(c).strip() else f"col_{i}" for i, c in enumerate(columns)]
    if not cols:
        cols = ["name", "description", "price", "reference", "brand", "category"]
    width = len(cols)

    out: List[List[Any]] = [cols]
    for row in rows:
        if not isinstance(row, Sequence) or isinstance(row, (str, bytes)):
            continue
        vals = list(row)[:width] + [None] * max(0, width - len(row))
        if not any(v is not None and str(v).strip() for v in vals):
            continue
        out.append(vals)
    return out


def _fallback_rows_from_text(text: str) -> List[List[Any]]:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return []

    delimiters = [";", "\t", "|"]
    delim_scores = {d: sum(1 for ln in lines[:30] if d in ln) for d in delimiters}
    best_delim = max(delim_scores, key=delim_scores.get)

    if delim_scores[best_delim] >= 3:
        parsed_rows = [line.split(best_delim) for line in lines[:200]]
        header = [c.strip() for c in parsed_rows[0]]
        data = [[c.strip() for c in r] for r in parsed_rows[1:]]
        return _normalize_table(header, data)

    header = ["name", "description", "price", "reference", "brand", "category"]
    rows: List[List[Any]] = []
    for line in lines[:200]:
        if len(line) < 3:
            continue
        rows.append([line, None, None, None, None, None])
    return [header, *rows] if rows else []
