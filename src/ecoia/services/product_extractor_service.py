import yaml
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from ecoia.db.models import Product, ProductFormat
from ecoia.services.field_mapping import json_safe
from ecoia.services.product_service import ProductService


class _PayloadHelpers:
    @staticmethod
    def _is_empty(value: Any) -> bool:
        return value is None or (isinstance(value, str) and not value.strip())

    @staticmethod
    def _set_nested_value(data: Dict[str, Any], path: str, value: Any) -> None:
        keys = path.split(".")
        cur = data
        for key in keys[:-1]:
            nxt = cur.get(key)
            if not isinstance(nxt, dict):
                nxt = {}
                cur[key] = nxt
            cur = nxt
        cur[keys[-1]] = value

    @staticmethod
    def _set_nested_default(data: Dict[str, Any], path: str, value: Any) -> None:
        keys = path.split(".")
        cur = data
        for key in keys[:-1]:
            nxt = cur.get(key)
            if not isinstance(nxt, dict):
                nxt = {}
                cur[key] = nxt
            cur = nxt
        leaf = keys[-1]
        if leaf not in cur or _PayloadHelpers._is_empty(cur.get(leaf)):
            cur[leaf] = value

    def merge_mapped_fields(self, mapped_fields: Dict[str, Any], processed_payload: Dict[str, Any]) -> None:
        for path, value in mapped_fields.items():
            if self._is_empty(value):
                continue
            if path in {"document_id", "supplier_id", "linked_data"}:
                continue
            self._set_nested_value(processed_payload, str(path), value)

    def apply_format_defaults(
        self,
        mapped_fields: Dict[str, Any],
        processed_payload: Dict[str, Any],
        format_config: Optional[Dict],
    ) -> None:
        defaults = self._collect_default_paths(self._normalize_format_fields(format_config))
        if not defaults:
            return
        for path, default_value in defaults.items():
            self._set_nested_default(processed_payload, path, default_value)
            if "." not in path and (path not in mapped_fields or self._is_empty(mapped_fields.get(path))):
                mapped_fields[path] = default_value

    @staticmethod
    def _normalize_format_fields(format_config: Optional[Dict]) -> List[Dict[str, Any]]:
        if not format_config or not isinstance(format_config, dict):
            return []
        fields = format_config.get("fields", {})
        if isinstance(fields, list):
            return [f for f in fields if isinstance(f, dict)]
        if isinstance(fields, dict):
            return [{"name": k, **v} if isinstance(v, dict) else {"name": k} for k, v in fields.items()]
        return []

    def _collect_default_paths(self, fields: List[Dict[str, Any]], prefix: str = "") -> Dict[str, Any]:
        defaults: Dict[str, Any] = {}
        for field in fields:
            name = field.get("name")
            if not name:
                continue
            path = f"{prefix}.{name}" if prefix else name
            if "default" in field:
                defaults[path] = field.get("default")
            sub_fields = field.get("fields")
            if isinstance(sub_fields, list):
                defaults.update(self._collect_default_paths(sub_fields, path))
            elif isinstance(sub_fields, dict):
                nested = [{"name": sk, **sv} if isinstance(sv, dict) else {"name": sk} for sk, sv in sub_fields.items()]
                defaults.update(self._collect_default_paths(nested, path))
        return defaults


class ProductExtractorService:
    def __init__(self, db: Session):
        self.db = db
        self.product_service = ProductService(db)
        self._helpers = _PayloadHelpers()

    def _make_json_serializable(self, obj: Any) -> Any:
        return json_safe(obj)

    async def analyze_sheets(
        self,
        file_path: str,
        parser=None,
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        from ecoia.services.sheet_analyzer import SheetAnalyzer

        return await SheetAnalyzer().analyze(file_path, parser=parser, provider=provider, model_name=model_name)

    def _build_cross_sheet_index(
        self,
        file_path: str,
        parser=None,
        on_progress: Optional[Callable] = None,
        analysis: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        from ecoia.services.cross_sheet_index import build_cross_sheet_index

        return build_cross_sheet_index(file_path, parser=parser, on_progress=on_progress, analysis=analysis)

    def extract_products_from_excel(
        self,
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
    ) -> List[Product]:
        from ecoia.services.excel_extractor import extract_products_from_excel

        return extract_products_from_excel(
            db=self.db,
            file_path=file_path,
            sheet_name=sheet_name,
            column_mapping=column_mapping,
            document_id=document_id,
            format_config=format_config,
            supplier_id=supplier_id,
            cross_sheet_index=cross_sheet_index,
            on_progress=on_progress,
            parser=parser,
            analysis=analysis,
            field_mapping_override=field_mapping_override,
            max_products=max_products,
            payload_helpers=self._helpers,
        )

    def extract_products_from_tables(
        self,
        file_path: str,
        document_id: UUID,
        supplier_id: Optional[UUID] = None,
        format_config: Optional[Dict] = None,
        on_progress: Optional[Callable] = None,
        field_mapping_override: Optional[Dict[str, Any]] = None,
        max_products: Optional[int] = None,
    ) -> List[Product]:
        from ecoia.services.table_extractor import (
            _extract_pdf_tables,
            _extract_docx_tables,
        )
        import os

        ext = os.path.splitext(file_path)[1].lower()
        if ext == ".csv":
            tables = self._extract_csv_tables(file_path)
        elif ext == ".pdf":
            tables = _extract_pdf_tables(file_path)
        elif ext == ".docx":
            tables = _extract_docx_tables(file_path)
        else:
            return []

        from ecoia.services.table_extractor import _process_tables

        return _process_tables(
            db=self.db,
            tables=tables,
            document_id=document_id,
            supplier_id=supplier_id,
            format_config=format_config,
            on_progress=on_progress,
            field_mapping_override=field_mapping_override,
            max_products=max_products,
            payload_helpers=self._helpers,
        )

    def _apply_format_defaults(
        self,
        mapped_fields: Dict[str, Any],
        processed_payload: Dict[str, Any],
        format_config: Optional[Dict],
    ) -> None:
        self._helpers.apply_format_defaults(mapped_fields, processed_payload, format_config)

    def _extract_csv_tables(self, file_path: str):
        from ecoia.services.table_extractor import _extract_csv_tables

        return _extract_csv_tables(file_path)

    def _extract_price(self, product_data: Dict) -> Optional[float]:
        from ecoia.services.field_mapping import extract_price

        return extract_price(product_data)

    def get_format_config(self, format_name: str) -> Optional[Dict]:
        try:
            fmt_id = UUID(format_name)
            db_fmt = self.db.get(ProductFormat, fmt_id)
            if db_fmt and isinstance(db_fmt.yaml_content, dict):
                return db_fmt.yaml_content
        except Exception:
            pass

        db_fmt = self.db.query(ProductFormat).filter(ProductFormat.name == format_name).first()
        if db_fmt and isinstance(db_fmt.yaml_content, dict):
            return db_fmt.yaml_content

        project_root = Path(__file__).resolve().parents[3]
        format_file = project_root / "configs" / "product_formats" / f"{format_name}.yaml"
        if format_file.exists():
            try:
                with open(format_file, "r") as f:
                    return yaml.safe_load(f)
            except Exception:
                return None
        return None

    def get_document_products(self, document_id: UUID) -> List[Product]:
        return self.db.query(Product).filter(Product.document_id == document_id).all()

    def delete_document_products(self, document_id: UUID) -> int:
        count = self.db.query(Product).filter(Product.document_id == document_id).delete()
        self.db.commit()
        return count
