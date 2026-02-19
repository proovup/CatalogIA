import csv
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from uuid import UUID

from ecoia.db.models import Product
from ecoia.services.field_mapping import (
    FIELD_MAP,
    extract_price,
    json_safe,
    parse_float,
)


def _extract_pdf_tables(file_path: str) -> List[List[list]]:
    try:
        import pdfplumber
    except ImportError:
        return []
    tables = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            for t in page.extract_tables():
                if t and len(t) >= 2:
                    tables.append(t)
    return tables


def _extract_docx_tables(file_path: str) -> List[List[list]]:
    try:
        import docx
    except ImportError:
        return []
    doc = docx.Document(file_path)
    tables = []
    for tbl in doc.tables:
        rows = [[cell.text.strip() for cell in row.cells] for row in tbl.rows]
        if len(rows) >= 2:
            tables.append(rows)
    return tables


def _extract_csv_tables(file_path: str) -> List[List[list]]:
    rows = []
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f)
        for row in reader:
            rows.append(row)
    return [rows] if len(rows) >= 2 else []


def _resolve_field_mapping_override(
    header: list,
    field_mapping_override: Dict[str, Any],
    base_mapping: Dict[str, int],
) -> Dict[str, int]:
    header_index = {str(c).strip().lower(): i for i, c in enumerate(header) if c is not None}
    resolved: Dict[str, int] = {}
    for field_name, raw_idx in field_mapping_override.items():
        idx: Optional[int] = None
        if isinstance(raw_idx, int):
            idx = raw_idx
        elif isinstance(raw_idx, str):
            candidate = raw_idx.strip()
            if candidate.isdigit():
                idx = int(candidate)
            else:
                idx = header_index.get(candidate.lower())
        if idx is None:
            continue
        if 0 <= idx < len(header):
            resolved[field_name] = idx
    if resolved:
        return {**base_mapping, **resolved}
    return base_mapping


def extract_products_from_tables(
    db,
    file_path: str,
    document_id: UUID,
    supplier_id: Optional[UUID] = None,
    format_config: Optional[Dict] = None,
    on_progress: Optional[Callable] = None,
    field_mapping_override: Optional[Dict[str, Any]] = None,
    max_products: Optional[int] = None,
    payload_helpers=None,
) -> List[Product]:
    import os

    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".pdf":
        tables = _extract_pdf_tables(file_path)
    elif ext == ".docx":
        tables = _extract_docx_tables(file_path)
    elif ext == ".csv":
        tables = _extract_csv_tables(file_path)
    else:
        return []

    return _process_tables(
        db=db,
        tables=tables,
        document_id=document_id,
        supplier_id=supplier_id,
        format_config=format_config,
        on_progress=on_progress,
        field_mapping_override=field_mapping_override,
        max_products=max_products,
        payload_helpers=payload_helpers,
    )


def _process_tables(
    db,
    tables: List[List[list]],
    document_id: UUID,
    supplier_id: Optional[UUID] = None,
    format_config: Optional[Dict] = None,
    on_progress: Optional[Callable] = None,
    field_mapping_override: Optional[Dict[str, Any]] = None,
    max_products: Optional[int] = None,
    payload_helpers=None,
) -> List[Product]:
    if not tables:
        return []

    now_s = str(datetime.utcnow())
    sid_s = str(supplier_id) if supplier_id else None
    fm = FIELD_MAP
    products = []

    for t_idx, table in enumerate(tables):
        if len(table) < 2:
            continue
        header = table[0]
        hdr_lower = [str(c).strip().lower() if c else f"col_{i}" for i, c in enumerate(header)]
        hdr_names = [str(c) if c else f"col_{i}" for i, c in enumerate(header)]

        col_map: Dict[str, int] = {}
        for i, cl in enumerate(hdr_lower):
            mf = fm.get(cl)
            if mf and mf not in col_map:
                col_map[mf] = i

        if field_mapping_override:
            col_map = _resolve_field_mapping_override(header, field_mapping_override, col_map)

        if not col_map:
            continue

        for ri, row in enumerate(table[1:], start=1):
            if not row or all(v is None or (isinstance(v, str) and not v.strip()) for v in row):
                continue
            rl = len(row)

            pd_row: Dict[str, Any] = {}
            for fn, ci in col_map.items():
                if 0 <= ci < rl:
                    pd_row[fn] = row[ci]
            for i, cl in enumerate(hdr_lower):
                if i < rl and row[i] is not None and cl not in pd_row:
                    mf = fm.get(cl)
                    if mf and mf not in pd_row:
                        pd_row[mf] = row[i]
                    elif not mf:
                        pd_row[cl] = row[i]

            if not any(v for v in pd_row.values() if v is not None and str(v).strip()):
                continue

            name = pd_row.get("name") or f"Produit T{t_idx + 1}-{ri}"
            desc = pd_row.get("description")
            price = extract_price(pd_row)
            cat = pd_row.get("category")
            ref = pd_row.get("reference")
            brand = pd_row.get("brand")

            processed_payload: Dict[str, Any] = {
                "document_id": document_id,
                "supplier_id": supplier_id,
                "name": name,
                "description": desc,
                "price": price,
                "category": cat,
                "reference": ref,
                "brand": brand,
            }

            if payload_helpers:
                payload_helpers.merge_mapped_fields(pd_row, processed_payload)
                payload_helpers.apply_format_defaults(pd_row, processed_payload, format_config)

            name = processed_payload.get("name") or name
            desc = processed_payload.get("description") or desc
            price = parse_float(processed_payload.get("price"))
            processed_payload["price"] = price
            cat = processed_payload.get("category") or cat
            ref = processed_payload.get("reference") or ref
            brand = processed_payload.get("brand") or brand

            row_dict = {hdr_names[i]: (row[i] if i < rl else None) for i in range(len(hdr_names))}

            products.append(
                Product(
                    document_id=document_id,
                    supplier_id=supplier_id,
                    name=name,
                    description=desc,
                    price=price,
                    category=cat,
                    reference=ref,
                    brand=brand,
                    status="draft",
                    raw_data=json_safe(
                        {
                            "row_data": row_dict,
                            "mapped_fields": pd_row,
                            "table_index": t_idx,
                            "row_index": ri,
                            "extracted_at": now_s,
                            "supplier_id": sid_s,
                        }
                    ),
                    processed_data=json_safe(processed_payload),
                )
            )

            if isinstance(max_products, int) and max_products > 0 and len(products) >= max_products:
                break

            if on_progress and len(products) % 200 == 0:
                on_progress(ri, 0, f"Table {t_idx + 1}: {len(products)} produits", len(products))

        if isinstance(max_products, int) and max_products > 0 and len(products) >= max_products:
            break

    if on_progress:
        on_progress(0, 0, f"Insertion de {len(products)} produits...", len(products))

    if products:
        db.add_all(products)
        db.flush()
        db.commit()

    return products
