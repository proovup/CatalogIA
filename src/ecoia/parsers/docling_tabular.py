from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence
import re

from ecoia.parsers.base import BaseParser


class DoclingTabularParser(BaseParser):
    """Parse non-Excel documents with Docling and expose them as pseudo-sheets."""

    SUPPORTED_EXTENSIONS = [".pdf", ".docx", ".doc", ".md", ".markdown", ".txt", ".csv"]
    SAMPLE_SIZE = 5

    def __init__(self):
        self._parsed_cache: Dict[str, Dict[str, Any]] = {}
        self._rows_cache: Dict[str, Dict[str, List[tuple]]] = {}

    def close(self):
        self._parsed_cache.clear()
        self._rows_cache.clear()

    def parse(self, file_path: str) -> Dict[str, Any]:
        self.validate_extension(file_path, self.SUPPORTED_EXTENSIONS)

        if file_path in self._parsed_cache:
            return self._parsed_cache[file_path]

        doc = self._convert_with_docling(file_path)
        tables = self._extract_tables(doc)
        if not tables:
            raise ValueError("Docling n'a detecte aucune table exploitable dans ce document")

        sheets: Dict[str, Dict[str, Any]] = {}
        rows_by_sheet: Dict[str, List[tuple]] = {}

        for idx, table in enumerate(tables, start=1):
            normalized = self._normalize_table_rows(table)
            if len(normalized) < 2:
                continue

            sheet_name = f"table_{idx}"
            header = tuple(normalized[0])
            data_rows = [tuple(r) for r in normalized[1:]]
            all_rows = [header, *data_rows]

            sheets[sheet_name] = {
                "columns": header,
                "samples": data_rows[: self.SAMPLE_SIZE],
                "total_rows": len(all_rows),
            }
            rows_by_sheet[sheet_name] = all_rows

        if not sheets:
            raise ValueError("Docling n'a detecte aucune table avec en-tetes et lignes")

        parsed = {
            "type": "tabular_doc",
            "sheets": sheets,
            "metadata": {
                "file_path": file_path,
                "sheet_names": list(sheets.keys()),
                "source": "docling",
            },
        }

        self._parsed_cache[file_path] = parsed
        self._rows_cache[file_path] = rows_by_sheet
        return parsed

    def get_all_rows(self, file_path: str, sheet_name: str, max_rows: Optional[int] = None):
        if file_path not in self._rows_cache:
            self.parse(file_path)

        rows = self._rows_cache.get(file_path, {}).get(sheet_name, [])
        if max_rows is not None:
            return rows[: max_rows + 1]
        return rows

    def _convert_with_docling(self, file_path: str) -> Any:
        try:
            from docling.document_converter import DocumentConverter
        except Exception as exc:
            raise RuntimeError("Docling n'est pas disponible. Installe docling==2.73.1") from exc

        converter = DocumentConverter()
        result = converter.convert(file_path)
        return getattr(result, "document", result)

    def _extract_tables(self, doc: Any) -> List[List[List[Any]]]:
        tables: List[List[List[Any]]] = []

        raw_tables = getattr(doc, "tables", None)
        if raw_tables is None and isinstance(doc, dict):
            raw_tables = doc.get("tables")

        if raw_tables:
            for raw_table in raw_tables:
                rows = self._table_to_rows(raw_table)
                if len(rows) >= 2:
                    tables.append(rows)

        if tables:
            return tables

        markdown_export = self._get_markdown_export(doc)
        if markdown_export:
            tables.extend(self._extract_markdown_tables(markdown_export))

        return [t for t in tables if len(t) >= 2]

    def _table_to_rows(self, table: Any) -> List[List[Any]]:
        df = self._table_to_dataframe(table)
        if df is not None:
            header = [str(c) if c is not None else "" for c in list(df.columns)]
            data_rows = [[v for v in row] for row in df.values.tolist()]
            return [header, *data_rows]

        if isinstance(table, dict):
            candidates = [table.get("rows"), table.get("data"), table.get("cells")]
            for cand in candidates:
                rows = self._coerce_rows(cand)
                if rows:
                    return rows

        for attr in ("rows", "data", "cells"):
            rows = self._coerce_rows(getattr(table, attr, None))
            if rows:
                return rows

        return []

    def _table_to_dataframe(self, table: Any):
        for method_name in ("export_to_dataframe", "to_dataframe", "to_pandas"):
            method = getattr(table, method_name, None)
            if callable(method):
                try:
                    return method()
                except Exception:
                    continue
        return None

    @staticmethod
    def _coerce_rows(raw_rows: Any) -> List[List[Any]]:
        if raw_rows is None:
            return []

        if isinstance(raw_rows, Sequence) and not isinstance(raw_rows, (str, bytes)):
            rows: List[List[Any]] = []
            for row in raw_rows:
                if isinstance(row, Sequence) and not isinstance(row, (str, bytes)):
                    rows.append([cell for cell in row])
                elif isinstance(row, dict):
                    rows.append(list(row.values()))
            return rows

        return []

    def _get_markdown_export(self, doc: Any) -> str:
        for method_name in ("export_to_markdown", "to_markdown"):
            method = getattr(doc, method_name, None)
            if callable(method):
                try:
                    out = method()
                    if isinstance(out, str) and out.strip():
                        return out
                except Exception:
                    continue

        if isinstance(doc, dict):
            for key in ("markdown", "text", "content"):
                val = doc.get(key)
                if isinstance(val, str) and val.strip():
                    return val

        for attr in ("markdown", "text", "content"):
            val = getattr(doc, attr, None)
            if isinstance(val, str) and val.strip():
                return val

        return ""

    def _extract_markdown_tables(self, markdown_text: str) -> List[List[List[str]]]:
        tables: List[List[List[str]]] = []
        current_block: List[str] = []

        for raw_line in markdown_text.splitlines():
            line = raw_line.rstrip()
            if "|" in line:
                current_block.append(line)
                continue

            if current_block:
                table = self._parse_markdown_block(current_block)
                if table:
                    tables.append(table)
                current_block = []

        if current_block:
            table = self._parse_markdown_block(current_block)
            if table:
                tables.append(table)

        return tables

    @staticmethod
    def _parse_markdown_block(lines: List[str]) -> List[List[str]]:
        rows: List[List[str]] = []
        sep_re = re.compile(r"^\s*\|?\s*:?[-]{3,}:?(\s*\|\s*:?[-]{3,}:?)*\s*\|?\s*$")

        for i, line in enumerate(lines):
            if i == 1 and sep_re.match(line):
                continue

            parts = [p.strip() for p in line.strip().strip("|").split("|")]
            if len(parts) < 2:
                continue
            rows.append(parts)

        return rows if len(rows) >= 2 else []

    @staticmethod
    def _normalize_table_rows(rows: List[List[Any]]) -> List[List[Any]]:
        normalized: List[List[Any]] = []
        max_cols = max((len(r) for r in rows), default=0)
        if max_cols == 0:
            return []

        for row in rows:
            padded = list(row) + [None] * (max_cols - len(row))
            normalized.append([cell if cell is not None else "" for cell in padded])

        # Remove fully empty rows
        compact = [r for r in normalized if any(str(v).strip() for v in r)]
        if len(compact) < 2:
            return []

        header = [str(v).strip() if str(v).strip() else f"col_{i}" for i, v in enumerate(compact[0])]
        out = [header]
        out.extend(compact[1:])
        return out
