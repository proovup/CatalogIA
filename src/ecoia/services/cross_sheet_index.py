from collections import Counter
from typing import Any, Callable, Dict, List, Optional, Set


def build_cross_sheet_index(
    file_path: str,
    parser=None,
    on_progress: Optional[Callable] = None,
    analysis: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build index: value_index maps 'col::val' -> {sheet: [row_idx, ...]} (supports 1:N)."""
    if parser is None:
        from ecoia.parsers import ParserFactory

        parser = ParserFactory.get_parser(file_path)

    parsed = parser.parse(file_path)
    sheets = parsed.get("sheets", {})
    if len(sheets) < 2:
        return {"shared_columns": set(), "value_index": {}, "sheet_headers": {}}

    forced_join_cols: Optional[Set[str]] = None
    if analysis:
        jc = analysis.get("join_columns", [])
        if jc:
            forced_join_cols = {str(c).strip().lower() for c in jc}

    sheet_headers: Dict[str, list] = {}
    sheet_col_maps: Dict[str, Dict[str, int]] = {}
    total_rows = 0
    for sn in sheets:
        rows = parser.get_all_rows(file_path, sn)
        if not rows:
            continue
        hdr = rows[0]
        sheet_headers[sn] = hdr
        total_rows += len(rows) - 1
        col_map = {}
        for i, c in enumerate(hdr):
            if c is not None:
                cl = str(c).strip().lower()
                if cl and len(cl) < 100:
                    col_map[cl] = i
        sheet_col_maps[sn] = col_map

    if on_progress:
        on_progress(0, 0, f"{len(sheets)} feuilles, {total_rows} lignes lues", 0)

    if forced_join_cols:
        shared: Set[str] = forced_join_cols
    else:
        cc: Counter = Counter()
        for cm in sheet_col_maps.values():
            for cn in cm:
                cc[cn] += 1
        shared = {c for c, n in cc.items() if n >= 2}

    if not shared:
        return {"shared_columns": set(), "value_index": {}, "sheet_headers": sheet_headers}

    vi: Dict[str, Dict[str, List[int]]] = {}
    indexed = 0
    for sn, cm in sheet_col_maps.items():
        rows = parser.get_all_rows(file_path, sn)
        if not rows or len(rows) < 2:
            continue
        shared_in = [(c, cm[c]) for c in shared if c in cm]
        if not shared_in:
            continue
        for ri, row in enumerate(rows[1:], start=1):
            if not row:
                continue
            rl = len(row)
            for cn, ci in shared_in:
                v = row[ci] if ci < rl else None
                if v is None:
                    continue
                ns = str(v).strip()
                if not ns:
                    continue
                key = f"{cn}::{ns}"
                if key not in vi:
                    vi[key] = {}
                    indexed += 1
                if sn not in vi[key]:
                    vi[key][sn] = []
                vi[key][sn].append(ri)

    col_multi: Counter = Counter()
    col_total: Counter = Counter()
    for key, sheet_map in vi.items():
        col = key.split("::", 1)[0]
        col_total[col] += 1
        if len(sheet_map) >= 2:
            col_multi[col] += 1

    validated: Set[str] = set()
    for col in shared:
        total = col_total.get(col, 0)
        multi = col_multi.get(col, 0)
        if total > 0 and (multi / total) >= 0.05:
            validated.add(col)

    if validated != shared:
        to_del = [k for k in vi if k.split("::", 1)[0] not in validated]
        for k in to_del:
            del vi[k]
        shared = validated
        indexed = len(vi)

    if on_progress:
        on_progress(0, 0, f"Index: {indexed} valeurs, {len(shared)} col. liees validees", 0)

    return {"shared_columns": shared, "value_index": vi, "sheet_headers": sheet_headers}
