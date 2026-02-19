import time as _time
from typing import Any, Dict, List, Optional
from uuid import UUID

from ecoia.db.database import SessionLocal
from ecoia.db.models import Document, Product
from ecoia.services.product_extractor_service import ProductExtractorService
from ecoia.services.source_preprocessor_service import SourcePreprocessorService
from ecoia.api.endpoints.products.helpers import auto_map_basic_fields, get_product_identifier

# In-memory job store for extraction progress
_extraction_jobs: Dict[str, Dict[str, Any]] = {}


def get_jobs_store() -> Dict[str, Dict[str, Any]]:
    return _extraction_jobs


def run_extraction_job(
    job_id: str,
    doc_id: UUID,
    file_path: str,
    filename: str,
    supplier_id: Optional[UUID],
    format_name: str,
    analysis: Optional[Dict[str, Any]] = None,
    field_mapping_override: Optional[Dict[str, Any]] = None,
    max_products: Optional[int] = None,
    source_mode: str = "document",
    presented_mode: str = "docling_ocr",
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
):
    import os as _os

    db = SessionLocal()
    parser = None
    t0 = _time.monotonic()

    def _elapsed():
        return round(_time.monotonic() - t0, 1)

    try:
        job = _extraction_jobs[job_id]
        doc = db.get(Document, doc_id)

        if doc:
            doc.status = "processing"
            doc.error_message = None
            db.commit()

        job["status"] = "preparing"
        job["message"] = "Nettoyage des anciens produits..."

        extractor = ProductExtractorService(db)
        extractor.delete_document_products(doc_id)
        format_config = extractor.get_format_config(format_name)

        ext = _os.path.splitext(file_path)[1].lower()
        fsize = _os.path.getsize(file_path) if _os.path.exists(file_path) else 0
        fsize_str = f"{fsize / 1024:.0f} Ko" if fsize < 1_048_576 else f"{fsize / 1_048_576:.1f} Mo"

        base_count = [0]

        def on_progress(current, total, msg, count):
            job["progress"] = current
            job["total"] = total
            job["message"] = f"[{_elapsed()}s] {msg}"
            job["count"] = base_count[0] + count

        job["message"] = f"[{_elapsed()}s] Ouverture du fichier ({fsize_str})..."

        parsed = None
        source_file_path = file_path
        non_excel_docling_ext = (".pdf", ".docx", ".doc", ".md", ".markdown", ".txt", ".csv")

        if source_mode == "presented_catalog":
            preprocessor = SourcePreprocessorService()
            job["status"] = "extracting"
            job["message"] = f"[{_elapsed()}s] Pré-traitement catalogue présenté ({presented_mode})..."
            pre = preprocessor.preprocess_presented_catalog(
                file_path=file_path,
                mode=presented_mode,
                provider=provider,
                model_name=model_name,
            )
            parser = pre.parser
            parsed = pre.parsed
        else:
            if ext in non_excel_docling_ext:
                job["status"] = "extracting"
                job["message"] = f"[{_elapsed()}s] Analyse Docling {ext.upper().lstrip('.')} ({fsize_str})..."
                try:
                    from ecoia.parsers.docling_tabular import DoclingTabularParser

                    parser = DoclingTabularParser()
                    parsed = parser.parse(file_path)
                except ValueError as e:
                    job["status"] = "error"
                    job["error"] = str(e)
                    job["done"] = True
                    if doc:
                        doc.status = "failed"
                        doc.error_message = str(e)
                        db.commit()
                    return
                except Exception:
                    job["message"] = f"[{_elapsed()}s] Docling indisponible, fallback extraction tabulaire..."
                    all_products = extractor.extract_products_from_tables(
                        file_path=file_path,
                        document_id=doc_id,
                        supplier_id=supplier_id,
                        format_config=format_config,
                        on_progress=on_progress,
                        field_mapping_override=field_mapping_override,
                        max_products=max_products,
                    )
                    job["status"] = "done"
                    job["message"] = f"Termine en {_elapsed()}s : {len(all_products)} produit(s)"
                    job["count"] = len(all_products)
                    job["done"] = True
                    if doc:
                        doc.status = "processed"
                        doc.error_message = None
                        db.commit()
                    return
            else:
                from ecoia.parsers import ParserFactory

                parser = ParserFactory.get_parser(file_path)
                parsed = parser.parse(file_path)

        all_products = run_tabular_extraction_pipeline(
            db=db,
            job=job,
            extractor=extractor,
            parser=parser,
            parsed=parsed,
            source_file_path=source_file_path,
            doc_id=doc_id,
            supplier_id=supplier_id,
            format_config=format_config,
            analysis=analysis,
            field_mapping_override=field_mapping_override,
            max_products=max_products,
            on_progress=on_progress,
            elapsed_fn=_elapsed,
        )

        job["status"] = "done"
        job["message"] = f"Termine en {_elapsed()}s : {len(all_products)} produit(s) extraits"
        job["count"] = len(all_products)
        job["done"] = True
        if doc:
            doc.status = "processed"
            doc.error_message = None
            db.commit()

    except Exception as e:
        import traceback

        traceback.print_exc()
        job = _extraction_jobs.get(job_id, {})
        job["status"] = "error"
        job["error"] = str(e)
        job["done"] = True
        doc = db.get(Document, doc_id)
        if doc:
            doc.status = "failed"
            doc.error_message = str(e)
            db.commit()
    finally:
        if parser and hasattr(parser, "close"):
            parser.close()
        db.close()


def run_website_extraction_job(
    job_id: str,
    doc_id: UUID,
    supplier_id: Optional[UUID],
    format_name: str,
    website: Dict[str, Any],
    max_products: Optional[int] = None,
    provider: Optional[str] = None,
    model_name: Optional[str] = None,
):
    db = SessionLocal()
    parser = None
    t0 = _time.monotonic()

    def _elapsed():
        return round(_time.monotonic() - t0, 1)

    try:
        job = _extraction_jobs[job_id]
        doc = db.get(Document, doc_id)

        if doc:
            doc.status = "processing"
            doc.error_message = None
            db.commit()

        extractor = ProductExtractorService(db)
        extractor.delete_document_products(doc_id)
        format_config = extractor.get_format_config(format_name)

        base_count = [0]

        def on_progress(current, total, msg, count):
            job["progress"] = current
            job["total"] = total
            job["message"] = f"[{_elapsed()}s] {msg}"
            job["count"] = base_count[0] + count

        job["status"] = "extracting"
        job["message"] = f"[{_elapsed()}s] Crawl website ({website.get('crawl_mode', 'manual')})..."

        preprocessor = SourcePreprocessorService()
        pre = preprocessor.preprocess_website(
            start_url=website.get("start_url", ""),
            crawl_mode=website.get("crawl_mode", "manual"),
            urls=website.get("urls") or [],
            max_pages=website.get("max_pages", 30),
            max_depth=website.get("max_depth", 2),
            provider=provider,
            model_name=model_name,
        )

        parser = pre.parser
        parsed = pre.parsed
        source_file_path = website.get("start_url") or "https://website.local/"

        all_products = run_tabular_extraction_pipeline(
            db=db,
            job=job,
            extractor=extractor,
            parser=parser,
            parsed=parsed,
            source_file_path=source_file_path,
            doc_id=doc_id,
            supplier_id=supplier_id,
            format_config=format_config,
            analysis=None,
            field_mapping_override=None,
            max_products=max_products,
            on_progress=on_progress,
            elapsed_fn=_elapsed,
        )

        job["status"] = "done"
        job["message"] = f"Termine en {_elapsed()}s : {len(all_products)} produit(s) extraits"
        job["count"] = len(all_products)
        job["done"] = True
        if doc:
            doc.status = "processed"
            doc.error_message = None
            if not doc.meta_data:
                doc.meta_data = {}
            doc.meta_data.update({"source_mode": "website", "website": website})
            db.commit()

    except Exception as e:
        import traceback

        traceback.print_exc()
        job = _extraction_jobs.get(job_id, {})
        job["status"] = "error"
        job["error"] = str(e)
        job["done"] = True
        doc = db.get(Document, doc_id)
        if doc:
            doc.status = "failed"
            doc.error_message = str(e)
            db.commit()
    finally:
        if parser and hasattr(parser, "close"):
            parser.close()
        db.close()


def run_tabular_extraction_pipeline(
    *,
    db,
    job: Dict[str, Any],
    extractor: ProductExtractorService,
    parser,
    parsed: Dict[str, Any],
    source_file_path: str,
    doc_id: UUID,
    supplier_id: Optional[UUID],
    format_config: Optional[Dict[str, Any]],
    analysis: Optional[Dict[str, Any]],
    field_mapping_override: Optional[Dict[str, Any]],
    max_products: Optional[int],
    on_progress,
    elapsed_fn,
) -> List[Product]:
    if parsed.get("type") not in ("excel", "tabular_doc"):
        raise ValueError("Type de source non supporté par le pipeline tabulaire")

    sheets = parsed.get("sheets", {})
    if not sheets:
        raise ValueError("Aucune feuille trouvée")

    total_rows = sum(si.get("total_rows", 0) for si in sheets.values())
    job["message"] = f"[{elapsed_fn()}s] {len(sheets)} feuille(s), {total_rows} lignes chargees"

    job["message"] = f"[{elapsed_fn()}s] Construction de l'index inter-feuilles..."
    cross_sheet_index = extractor._build_cross_sheet_index(
        source_file_path,
        parser=parser,
        on_progress=on_progress,
        analysis=analysis,
    )

    shared_cols = cross_sheet_index.get("shared_columns", set())
    vi_size = len(cross_sheet_index.get("value_index", {}))
    job["message"] = f"[{elapsed_fn()}s] Index: {len(shared_cols)} col. partagees, {vi_size} valeurs"

    if analysis and analysis.get("master_sheet"):
        master_name = analysis["master_sheet"]
        if master_name not in sheets:
            raise ValueError(f"Feuille maitre '{master_name}' non trouvee")
        cols = sheets[master_name].get("columns", [])
        cm = auto_map_basic_fields(cols)
        if field_mapping_override:
            cm = {**cm, **field_mapping_override}
        if not cm:
            cm = {f"col_{i}": i for i in range(len(cols))}
        extractable = [(master_name, cm, sheets[master_name].get("total_rows", 0))]
        sec_sheets = [
            s for s in analysis.get("sheets", []) if s.get("name") != master_name and s.get("role") != "metadata"
        ]
        sec_names = (
            ", ".join(f"'{s['name']}' ({s.get('relation', '?')})" for s in sec_sheets) if sec_sheets else "aucune"
        )
        pri_names = f"'{master_name}'"
    else:
        all_mapped = []
        for sn, si in sheets.items():
            cols = si.get("columns", [])
            if not cols:
                continue
            cm = auto_map_basic_fields(cols)
            if cm:
                all_mapped.append((sn, cm, si.get("total_rows", 0)))

        if not all_mapped:
            raise ValueError("Aucune feuille avec des colonnes produit detectee")

        primary = [(sn, cm, tr) for sn, cm, tr in all_mapped if "name" in cm]
        secondary = [(sn, cm, tr) for sn, cm, tr in all_mapped if "name" not in cm]

        if not primary:
            all_mapped.sort(key=lambda x: len(x[1]), reverse=True)
            primary = [all_mapped[0]]
            secondary = all_mapped[1:]

        primary.sort(key=lambda x: x[2], reverse=True)
        chosen_primary = primary[0]
        if field_mapping_override:
            chosen_primary = (chosen_primary[0], {**chosen_primary[1], **field_mapping_override}, chosen_primary[2])

        extractable = [chosen_primary]
        sec_names = ", ".join(f"'{s[0]}'" for s in secondary) if secondary else "aucune"
        pri_names = f"'{chosen_primary[0]}'"

    job["status"] = "extracting"
    job["message"] = f"[{elapsed_fn()}s] Primaire(s): {pri_names} | Enrichissement: {sec_names}"

    seen = set()
    all_products = []
    remaining_products = max_products if isinstance(max_products, int) and max_products > 0 else None

    for si, (sn, cm, srows) in enumerate(extractable):
        if remaining_products is not None and remaining_products <= 0:
            break
        t_sheet = _time.monotonic()
        job["message"] = f"[{elapsed_fn()}s] Feuille {si + 1}/{len(extractable)}: '{sn}' ({srows} lignes)..."

        sheet_products = extractor.extract_products_from_excel(
            file_path=source_file_path,
            sheet_name=sn,
            column_mapping=cm,
            document_id=doc_id,
            format_config=format_config,
            supplier_id=supplier_id,
            cross_sheet_index=cross_sheet_index,
            on_progress=on_progress,
            parser=parser,
            analysis=analysis,
            field_mapping_override=field_mapping_override,
            max_products=remaining_products,
        )

        dt_sheet = round(_time.monotonic() - t_sheet, 1)
        job["message"] = f"[{elapsed_fn()}s] '{sn}': {len(sheet_products)} produits en {dt_sheet}s"

        dupes = []
        for p in sheet_products:
            ident = get_product_identifier(p)
            if ident and ident in seen:
                dupes.append(p.id)
                continue
            if ident:
                seen.add(ident)
            all_products.append(p)

        if dupes:
            from sqlalchemy import delete as sa_delete

            db.execute(sa_delete(Product).where(Product.id.in_(dupes)))
            db.commit()
            job["message"] = f"[{elapsed_fn()}s] '{sn}': {len(dupes)} doublons retires"

        job["count"] = len(all_products)
        if remaining_products is not None:
            remaining_products = max(0, remaining_products - len(sheet_products))

    return all_products
