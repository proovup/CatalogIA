"""
Enrichment Service — Parse documents and enrich existing products with supplementary data.
"""

import json
import os
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import select

from ecoia.db.models import Document, EnrichmentDocument, Product


class EnrichmentService:
    """Service for enriching existing products from supplementary documents."""

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def list_enrichment_documents(
        self,
        product_id: Optional[UUID] = None,
        document_id: Optional[UUID] = None,
    ) -> List[EnrichmentDocument]:
        """List enrichment documents, optionally filtered by product or document."""
        query = select(EnrichmentDocument).order_by(EnrichmentDocument.created_at.desc())
        if product_id:
            query = query.where(EnrichmentDocument.product_id == product_id)
        if document_id:
            query = query.where(EnrichmentDocument.document_id == document_id)
        return self.db.execute(query).scalars().all()

    def get_enrichment_document(self, enrichment_id: UUID) -> Optional[EnrichmentDocument]:
        return self.db.get(EnrichmentDocument, enrichment_id)

    def delete_enrichment_document(self, enrichment_id: UUID) -> bool:
        ed = self.db.get(EnrichmentDocument, enrichment_id)
        if not ed:
            return False
        self.db.delete(ed)
        self.db.commit()
        return True

    # ------------------------------------------------------------------
    # Core enrichment pipeline
    # ------------------------------------------------------------------

    def run_enrichment(
        self,
        document_id: UUID,
        product_ids: List[UUID],
        enrichment_type: str = "other",
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
        on_progress: Optional[Callable] = None,
    ) -> List[EnrichmentDocument]:
        """
        Main enrichment pipeline:
        1. Parse the uploaded document
        2. Extract structured data
        3. Match data to target products
        4. Merge into product processed_data
        """
        doc = self.db.get(Document, document_id)
        if not doc:
            raise ValueError(f"Document {document_id} not found")
        if not doc.file_path or not os.path.exists(doc.file_path):
            raise ValueError(f"Document file not found on disk: {doc.file_path}")

        # Step 1: Parse
        if on_progress:
            on_progress(10, 100, "Parsing du document...", 0)

        parsed_data = self._parse_document(doc.file_path)

        if on_progress:
            on_progress(30, 100, "Données extraites, extraction structurée...", 0)

        # Step 2: Extract structured info via AI
        extracted = self._extract_structured_data(
            parsed_data=parsed_data,
            filename=doc.filename,
            enrichment_type=enrichment_type,
            provider=provider,
            model_name=model_name,
        )

        if on_progress:
            on_progress(50, 100, f"Données structurées extraites, matching avec {len(product_ids)} produit(s)...", 0)

        # Step 3: Load target products
        products = self.db.execute(select(Product).where(Product.id.in_(product_ids))).scalars().all()

        if not products:
            raise ValueError("Aucun produit cible trouvé")

        # Step 4: Match extracted data to products
        matches = self._match_to_products(
            extracted_items=extracted,
            products=products,
            provider=provider,
            model_name=model_name,
        )

        if on_progress:
            on_progress(70, 100, f"{len(matches)} correspondance(s) trouvée(s), enrichissement...", 0)

        # Step 5: Create enrichment records and merge data
        enrichment_docs = []
        for i, (product, matched_data, confidence, method) in enumerate(matches):
            ed = EnrichmentDocument(
                id=uuid.uuid4(),
                document_id=document_id,
                product_id=product.id,
                enrichment_type=enrichment_type,
                extracted_data=self._make_serializable(matched_data),
                status="completed",
                match_confidence=confidence,
                match_method=method,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            self.db.add(ed)

            # Merge extracted data into product's processed_data
            self._merge_into_product(product, matched_data, enrichment_type)

            enrichment_docs.append(ed)

            if on_progress:
                pct = 70 + int((i + 1) / len(matches) * 25)
                on_progress(pct, 100, f"Produit {i + 1}/{len(matches)} enrichi", i + 1)

        doc.status = "processed"
        self.db.commit()

        if on_progress:
            on_progress(100, 100, f"Terminé : {len(enrichment_docs)} produit(s) enrichi(s)", len(enrichment_docs))

        return enrichment_docs

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _parse_document(self, file_path: str) -> Dict[str, Any]:
        """Parse a document using the existing parser infrastructure."""
        ext = os.path.splitext(file_path)[1].lower()

        docling_ext = (".pdf", ".docx", ".doc", ".md", ".markdown", ".txt", ".csv")

        if ext in docling_ext:
            try:
                from ecoia.parsers.docling_tabular import DoclingTabularParser

                parser = DoclingTabularParser()
                parsed = parser.parse(file_path)
                return parsed
            except Exception:
                # Fallback to basic text extraction
                pass

        if ext in (".xlsx", ".xls"):
            from ecoia.parsers import ParserFactory

            parser = ParserFactory.get_parser(file_path)
            return parser.parse(file_path)

        # Default: read as text
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            return {"type": "text", "content": content, "filename": os.path.basename(file_path)}
        except Exception:
            return {"type": "unknown", "content": "", "filename": os.path.basename(file_path)}

    def _extract_structured_data(
        self,
        parsed_data: Dict[str, Any],
        filename: str,
        enrichment_type: str,
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Extract structured product-related information from parsed document data."""
        from ecoia.core.llm_factory import LLMFactory
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_core.output_parsers import JsonOutputParser

        # Build content summary for the LLM
        content_summary = self._build_content_summary(parsed_data)

        type_labels = {
            "notice": "notice technique / mode d'emploi",
            "catalogue": "catalogue produit / brochure commerciale",
            "fiche_technique": "fiche technique / spécifications",
            "other": "document complémentaire",
        }
        type_label = type_labels.get(enrichment_type, enrichment_type)

        llm = LLMFactory.get_llm(
            provider=provider,
            model_name=model_name,
            temperature=0,
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """Tu es un expert en extraction de données produit.
On te donne le contenu d'un document de type "{doc_type}" (fichier: {filename}).
Ton rôle est d'extraire TOUTES les informations produit structurées présentes dans ce document.

RÈGLES:
1. Retourne un tableau JSON d'objets, chaque objet représentant un produit ou une section produit trouvé(e)
2. Pour chaque entrée, inclus tous les champs trouvés : nom, référence, description, caractéristiques techniques, dimensions, poids, certifications, etc.
3. Si le document concerne un seul produit, retourne un tableau avec un seul élément
4. Utilise des noms de champs en snake_case français ou anglais
5. Inclus un champ "reference" ou "name" si disponible pour faciliter le matching
6. NE JAMAIS INVENTER de données — extrais uniquement ce qui est dans le document
7. Pour les tableaux de caractéristiques, aplatir en champs individuels (ex: "poids": "2.5 kg")

Retourne UNIQUEMENT un tableau JSON valide.""",
                ),
                (
                    "human",
                    """Contenu du document:
{content}

Extrais toutes les informations produit en JSON.""",
                ),
            ]
        )

        import asyncio

        chain = prompt | llm | JsonOutputParser()

        # Run sync since we may be in a thread
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as pool:
                    result = pool.submit(
                        lambda: asyncio.run(
                            chain.ainvoke(
                                {
                                    "doc_type": type_label,
                                    "filename": filename,
                                    "content": content_summary[:8000],
                                }
                            )
                        )
                    ).result()
            else:
                result = asyncio.run(
                    chain.ainvoke(
                        {
                            "doc_type": type_label,
                            "filename": filename,
                            "content": content_summary[:8000],
                        }
                    )
                )
        except Exception:
            # If async fails, try sync invoke
            try:
                result = chain.invoke(
                    {
                        "doc_type": type_label,
                        "filename": filename,
                        "content": content_summary[:8000],
                    }
                )
            except Exception:
                # Last resort: return raw content as single item
                return [{"raw_content": content_summary[:4000], "source": filename}]

        if isinstance(result, dict):
            result = [result]
        if not isinstance(result, list):
            return [{"raw_content": str(result), "source": filename}]

        return result

    def _match_to_products(
        self,
        extracted_items: List[Dict[str, Any]],
        products: List[Product],
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> List[tuple]:
        """
        Match extracted data items to target products.
        Returns list of (product, matched_data, confidence, method) tuples.
        """
        matches = []

        # If only one product and one extracted item, direct match
        if len(products) == 1 and len(extracted_items) == 1:
            matches.append((products[0], extracted_items[0], 1.0, "direct"))
            return matches

        # If only one product, merge all extracted items
        if len(products) == 1:
            merged = {}
            for item in extracted_items:
                merged.update(item)
            matches.append((products[0], merged, 1.0, "direct"))
            return matches

        # Try reference-based matching first
        ref_fields = ["reference", "ref", "sku", "ean", "ean13", "gtin", "code", "code_produit"]
        product_ref_map = {}
        for p in products:
            refs = set()
            if p.reference:
                refs.add(str(p.reference).strip().lower())
            if p.raw_data and isinstance(p.raw_data, dict):
                mapped = p.raw_data.get("mapped_fields", {})
                for rf in ref_fields:
                    v = mapped.get(rf)
                    if v:
                        refs.add(str(v).strip().lower())
            for ref in refs:
                product_ref_map[ref] = p

        matched_products = set()
        unmatched_items = []

        for item in extracted_items:
            matched = False
            for rf in ref_fields:
                val = item.get(rf)
                if val:
                    val_lower = str(val).strip().lower()
                    if val_lower in product_ref_map:
                        product = product_ref_map[val_lower]
                        matches.append((product, item, 0.95, "reference"))
                        matched_products.add(product.id)
                        matched = True
                        break
            if not matched:
                unmatched_items.append(item)

        # For unmatched items + products, try name-based matching
        unmatched_products = [p for p in products if p.id not in matched_products]

        if unmatched_items and unmatched_products:
            # Try simple name matching
            for item in unmatched_items:
                item_name = str(item.get("name", item.get("nom", ""))).strip().lower()
                if not item_name:
                    continue
                best_match = None
                best_score = 0
                for p in unmatched_products:
                    p_name = str(p.name or "").strip().lower()
                    if not p_name:
                        continue
                    # Simple substring matching
                    if item_name in p_name or p_name in item_name:
                        score = 0.8
                    elif any(w in p_name for w in item_name.split() if len(w) > 3):
                        score = 0.6
                    else:
                        score = 0
                    if score > best_score:
                        best_score = score
                        best_match = p

                if best_match and best_score >= 0.6:
                    matches.append((best_match, item, best_score, "name_match"))
                    matched_products.add(best_match.id)
                    unmatched_products = [p for p in unmatched_products if p.id != best_match.id]

        # For remaining unmatched: if there are still unmatched items,
        # distribute them to all remaining unmatched products
        still_unmatched_items = [item for item in unmatched_items if not any(m[1] is item for m in matches)]

        if still_unmatched_items and unmatched_products:
            # Merge all unmatched items and apply to all remaining products
            merged_data = {}
            for item in still_unmatched_items:
                merged_data.update(item)
            for p in unmatched_products:
                matches.append((p, merged_data, 0.5, "broadcast"))

        # If no matches at all, broadcast to all products
        if not matches:
            merged_data = {}
            for item in extracted_items:
                merged_data.update(item)
            for p in products:
                matches.append((p, merged_data, 0.3, "broadcast"))

        return matches

    def _merge_into_product(
        self,
        product: Product,
        enrichment_data: Dict[str, Any],
        enrichment_type: str,
    ) -> None:
        """Merge enrichment data into a product's processed_data."""
        if not product.processed_data:
            product.processed_data = {}

        # Store enrichment under a dedicated key to avoid overwriting existing data
        enrichments = product.processed_data.get("enrichments", [])
        if not isinstance(enrichments, list):
            enrichments = []

        enrichments.append(
            {
                "type": enrichment_type,
                "data": enrichment_data,
                "enriched_at": datetime.utcnow().isoformat(),
            }
        )

        product.processed_data = {
            **product.processed_data,
            "enrichments": enrichments,
        }

        # Also merge top-level fields that don't already exist
        skip_fields = {"reference", "ref", "name", "nom", "raw_content", "source"}
        for key, value in enrichment_data.items():
            if key in skip_fields:
                continue
            if value is None or (isinstance(value, str) and not value.strip()):
                continue
            # Only add if not already present in processed_data
            if key not in product.processed_data or product.processed_data.get(key) in (None, "", []):
                product.processed_data[key] = value

        product.updated_at = datetime.utcnow()

    def _build_content_summary(self, parsed_data: Dict[str, Any]) -> str:
        """Build a text summary from parsed data for LLM consumption."""
        doc_type = parsed_data.get("type", "unknown")

        if doc_type == "text":
            return parsed_data.get("content", "")[:8000]

        if doc_type in ("excel", "tabular_doc"):
            sheets = parsed_data.get("sheets", {})
            parts = []
            for sn, info in sheets.items():
                cols = info.get("columns", [])
                parts.append(f"=== Feuille: {sn} ===")
                parts.append(f"Colonnes: {', '.join(str(c) for c in cols if c)}")

                # Include sample rows if available
                rows = info.get("rows", [])
                if rows:
                    for row in rows[:20]:
                        parts.append(" | ".join(str(v) if v is not None else "" for v in row))

            return "\n".join(parts)[:8000]

        # For other types, try to extract text content
        content = parsed_data.get("content", "")
        if content:
            return str(content)[:8000]

        return json.dumps(parsed_data, default=str, ensure_ascii=False)[:8000]

    @staticmethod
    def _make_serializable(obj: Any) -> Any:
        """Make an object JSON serializable."""
        if isinstance(obj, UUID):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, dict):
            return {k: EnrichmentService._make_serializable(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [EnrichmentService._make_serializable(v) for v in obj]
        return obj
