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


def resolve_field_mapping_override(
    header_row: list,
    field_mapping_override: Dict[str, Any],
    base_mapping: Dict[str, int],
) -> Dict[str, int]:
    header_index = {str(c).strip().lower(): i for i, c in enumerate(header_row) if c is not None and str(c).strip()}
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
        if 0 <= idx < len(header_row):
            resolved[field_name] = idx
    if resolved:
        return {**base_mapping, **resolved}
    return base_mapping


def extract_products_from_excel(
    db,
    file_path: str,
    sheet_name: str,
    column_mapping: Dict[str, int],
    document_id: UUID,
    format_config: Optional[Dict] = None,
    supplier_id: Optional[UUID] = None,
    cross_sheet_index: Optional[Dict[str, Any]] = None,
    on_progress: Optional[Callable] = None,
    parser=None,
    analysis: Optional[Dict[str, Any]] = None,
    field_mapping_override: Optional[Dict[str, Any]] = None,
    max_products: Optional[int] = None,
    payload_helpers=None,
) -> List[Product]:
    from ecoia.services.cross_sheet_index import build_cross_sheet_index

    if parser is None:
        from ecoia.parsers import ParserFactory

        parser = ParserFactory.get_parser(file_path)
    if cross_sheet_index is None:
        cross_sheet_index = build_cross_sheet_index(file_path, parser=parser, analysis=analysis)

    all_rows = parser.get_all_rows(file_path, sheet_name)
    if not all_rows or len(all_rows) < 2:
        return []

    header_row = all_rows[0]
    data_rows = all_rows[1:]
    total = len(data_rows)

    if field_mapping_override:
        column_mapping = resolve_field_mapping_override(header_row, field_mapping_override, column_mapping)

    hdr_names = [str(c) if c is not None else f"col_{i}" for i, c in enumerate(header_row)]
    ncols = len(hdr_names)

    shared = cross_sheet_index.get("shared_columns", set())
    vi = cross_sheet_index.get("value_index", {})
    has_idx = bool(shared and vi)

    sheet_roles = {}
    sheet_relations = {}
    if analysis:
        for s in analysis.get("sheets", []):
            sheet_roles[s.get("name", "")] = s.get("role", "enrichment")
            sheet_relations[s.get("name", "")] = s.get("relation", "1:1")

    shared_hdr = []
    if has_idx:
        for i, c in enumerate(header_row):
            if c is not None:
                cl = str(c).strip().lower()
                if cl in shared:
                    shared_hdr.append((cl, i))

    fm = FIELD_MAP
    now_s = str(datetime.utcnow())
    sid_s = str(supplier_id) if supplier_id else None

    _linked_hdrs = {}
    if has_idx:
        for sn_h, hdr_h in cross_sheet_index.get("sheet_headers", {}).items():
            if sn_h != sheet_name and hdr_h:
                mapped = []
                for li, lc in enumerate(hdr_h):
                    if lc is not None:
                        lcl = str(lc).strip().lower()
                        mapped.append((li, lcl, fm.get(lcl)))
                    else:
                        mapped.append((li, None, None))
                _linked_hdrs[sn_h] = (
                    mapped,
                    [str(c) if c is not None else f"col_{i}" for i, c in enumerate(hdr_h)],
                )

    products = []

    for ri, row in enumerate(data_rows):
        if not row or all(v is None for v in row):
            continue
        rl = len(row)

        pd_row = {}
        for fn, ci in column_mapping.items():
            if isinstance(ci, int) and 0 <= ci < rl:
                pd_row[fn] = row[ci]

        src = [{"sheet": sheet_name, "row": ri + 1}]
        linked_data_by_sheet: Dict[str, List[Dict]] = {}

        if has_idx:
            for cl, ci in shared_hdr:
                v = row[ci] if ci < rl else None
                if v is None:
                    continue
                ns = str(v).strip()
                if not ns:
                    continue
                entries = vi.get(f"{cl}::{ns}")
                if not entries:
                    continue
                for esn, eri_list in entries.items():
                    if esn == sheet_name:
                        continue
                    role = sheet_roles.get(esn, "enrichment")
                    if role == "metadata":
                        continue
                    if analysis:
                        sheet_cfg = next((s for s in analysis.get("sheets", []) if s.get("name") == esn), None)
                        if sheet_cfg and sheet_cfg.get("excluded") is True:
                            continue
                    linked_rows_all = parser.get_all_rows(file_path, esn)
                    if not linked_rows_all:
                        continue
                    hdr_info = _linked_hdrs.get(esn)
                    if not hdr_info:
                        continue
                    hdr_map, _ = hdr_info

                    for eri in eri_list:
                        if eri >= len(linked_rows_all):
                            continue
                        lrow = linked_rows_all[eri]
                        lrl = len(lrow)
                        src.append({"sheet": esn, "row": eri, "key": f"{cl}::{ns}"})

                        lrow_dict = {}
                        for li, lcl, mf in hdr_map:
                            if lcl is None:
                                continue
                            lv = lrow[li] if li < lrl else None
                            if lv is None:
                                continue
                            lrow_dict[lcl] = lv

                        if esn not in linked_data_by_sheet:
                            linked_data_by_sheet[esn] = []
                        linked_data_by_sheet[esn].append(lrow_dict)

                        relation = sheet_relations.get(esn, "1:1")
                        if relation == "1:1" or len(linked_data_by_sheet[esn]) == 1:
                            for li, lcl, mf in hdr_map:
                                if lcl is None:
                                    continue
                                lv = lrow[li] if li < lrl else None
                                if lv is None:
                                    continue
                                if mf and mf not in pd_row:
                                    pd_row[mf] = lv
                                elif not mf and lcl not in pd_row:
                                    pd_row[lcl] = lv

        if not any(v for k, v in pd_row.items() if v is not None and str(v).strip()):
            continue

        name = pd_row.get("name") or pd_row.get("nom") or f"Produit {ri + 1}"
        desc = pd_row.get("description") or pd_row.get("desc")
        price = extract_price(pd_row)
        cat = pd_row.get("category") or pd_row.get("categorie")
        ref = pd_row.get("reference") or pd_row.get("sku") or pd_row.get("ref")
        brand = pd_row.get("brand") or pd_row.get("marque")

        processed_payload = {
            "document_id": document_id,
            "supplier_id": supplier_id,
            "name": name,
            "description": desc,
            "price": price,
            "category": cat,
            "reference": ref,
            "brand": brand,
            "linked_data": linked_data_by_sheet,
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

        row_dict = {hdr_names[i]: (row[i] if i < rl else None) for i in range(ncols)}

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
                        "source_sheets": src,
                        "linked_data": linked_data_by_sheet,
                        "row_index": ri + 1,
                        "sheet_name": sheet_name,
                        "extracted_at": now_s,
                        "supplier_id": sid_s,
                    }
                ),
                processed_data=json_safe(processed_payload),
            )
        )

        if isinstance(max_products, int) and max_products > 0 and len(products) >= max_products:
            break

        if on_progress and len(products) % 50 == 0:
            on_progress(
                ri + 1,
                total,
                f"Feuille '{sheet_name}': {len(products)} produits ({ri + 1}/{total} lignes)",
                len(products),
            )

    if on_progress:
        on_progress(total, total, f"Feuille '{sheet_name}': insertion de {len(products)} produits...", len(products))

    if products:
        db.add_all(products)
        db.flush()
        db.commit()

    return products
