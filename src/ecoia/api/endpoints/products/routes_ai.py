import json
import os
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ecoia.db.database import get_db
from ecoia.db.models import Document, Product
from ecoia.services.product_extractor_service import ProductExtractorService
from ecoia.services.classification_service import ClassificationService
from ecoia.schemas.classification import CategoryNode, ClassificationRequest
from ecoia.api.endpoints.products.schemas import (
    AnalyzeRequest,
    ClassifyRequest,
    RegenerateFieldRequest,
    RegenerateRequest,
)
from ecoia.api.endpoints.products.helpers import product_to_out

router = APIRouter()

DEFAULT_CATEGORIES = [
    CategoryNode(
        name="Maison",
        children=[
            CategoryNode(
                name="Cuisine",
                children=[CategoryNode(name="Ustensiles"), CategoryNode(name="Électroménager")],
            ),
            CategoryNode(
                name="Éclairage",
                children=[CategoryNode(name="Ampoules"), CategoryNode(name="Lampes")],
            ),
        ],
    )
]


@router.post("/analyze")
async def analyze_document(req: AnalyzeRequest, db: Session = Depends(get_db)):
    doc = db.get(Document, UUID(req.document_id))
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if not doc.file_path or not os.path.exists(doc.file_path):
        raise HTTPException(status_code=404, detail="Document file not found on disk")

    doc.status = "processing"
    doc.error_message = None
    db.commit()

    ext = os.path.splitext(doc.file_path)[1].lower()
    if ext not in (".xlsx", ".xls"):
        doc.status = "processed"
        db.commit()
        return {"skip_analysis": True, "reason": "Not an Excel file", "file_type": ext}

    extractor = ProductExtractorService(db)
    try:
        analysis = await extractor.analyze_sheets(
            file_path=doc.file_path,
            provider=req.provider,
            model_name=req.model_name,
        )
    except Exception as e:
        doc.status = "failed"
        doc.error_message = str(e)
        db.commit()
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

    doc.status = "processed"
    doc.error_message = None
    db.commit()

    return {"document_id": str(doc.id), "filename": doc.filename, "analysis": analysis}


@router.post("/{product_id}/classify")
async def classify_product(product_id: UUID, req: ClassifyRequest, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    text = f"{product.name or ''} {product.description or ''}"
    if not text.strip():
        raise HTTPException(status_code=400, detail="Product has no name or description to classify")

    service = ClassificationService(provider=req.provider, model_name=req.model_name)
    request = ClassificationRequest(
        product_title=product.name or "",
        product_description=product.description or "",
        categories=DEFAULT_CATEGORIES,
        provider=req.provider,
        model_name=req.model_name,
    )
    result = await service.classify(request)

    if result.category_path:
        product.category = " > ".join(result.category_path)
        db.commit()
        db.refresh(product)

    doc = db.get(Document, product.document_id)
    return {
        "classification": {"category_path": result.category_path, "confidence": result.confidence},
        "product": product_to_out(product, doc.filename if doc else ""),
    }


@router.post("/{product_id}/regenerate")
async def regenerate_product(product_id: UUID, req: RegenerateRequest, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    from ecoia.core.llm_factory import LLMFactory
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import JsonOutputParser

    extractor = ProductExtractorService(db)
    format_config = extractor.get_format_config(req.format_name)

    fields_lines, defaults, consts = _build_fields_spec(format_config)
    fields_desc = "\n".join(fields_lines)

    raw_data_str = json.dumps(product.raw_data or {}, default=str, ensure_ascii=False)
    current_processed = json.dumps(product.processed_data or {}, default=str, ensure_ascii=False)

    llm = LLMFactory.get_llm(provider=req.provider, model_name=req.model_name, temperature=0)
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """Tu es un expert en génération de fiches produits e-commerce.
À partir des données brutes fournies, génère une fiche produit COMPLÈTE avec TOUS les champs listés ci-dessous.

RÈGLES:
1. Retourne un JSON PLAT — chaque valeur est une string ou un nombre, JAMAIS d'objet ou tableau imbriqué.
2. Tu DOIS remplir TOUS les champs listés. Ne laisse AUCUN champ vide.
3. Pour les champs de DONNÉES (name, price, reference, brand, etc.) : utilise les données source fournies.
4. Pour les champs marqués [IA: ...] : GÉNÈRE le contenu toi-même en suivant l'instruction. C'est ton rôle principal.
5. Si un champ de données n'a pas de valeur dans la source, mets une string vide "" ou null — mais NE L'OMETS PAS du JSON.
6. NE JAMAIS INVENTER d'URL, d'image, de lien ou de certification qui ne sont pas dans les données source.
7. Les champs IA comme description_short, meta_title, meta_description, link_rewrite, seo_keywords, family, etc. DOIVENT être générés par toi à partir du contexte produit.

CHAMPS À REMPLIR:
{fields}

Retourne UNIQUEMENT un JSON valide et PLAT avec TOUS les champs ci-dessus remplis.""",
            ),
            (
                "human",
                """Données du produit à régénérer:
Nom: {name}
Description: {description}
Prix: {price}
Catégorie: {category}
Référence: {reference}
Marque: {brand}
Données source complètes: {raw_data}
Données traitées existantes: {processed_data}

Génère la fiche produit COMPLÈTE en JSON PLAT. Remplis TOUS les champs, y compris les champs IA.""",
            ),
        ]
    )

    chain = prompt | llm | JsonOutputParser()
    result = await chain.ainvoke(
        {
            "fields": fields_desc,
            "name": product.name or "",
            "description": product.description or "",
            "price": str(product.price or ""),
            "category": product.category or "",
            "reference": product.reference or "",
            "brand": product.brand or "",
            "raw_data": raw_data_str[:6000],
            "processed_data": current_processed[:2000],
        }
    )

    if isinstance(result, dict):
        for k, v in consts.items():
            result[k] = v
        for k, v in defaults.items():
            if k not in result or result[k] is None or result[k] == "":
                result[k] = v

        result = _flatten_result(result)

        if result.get("name"):
            product.name = _to_str(result["name"])
        if result.get("description"):
            product.description = _to_str(result["description"])
        pv = _to_float(result.get("price"))
        if pv is not None:
            product.price = pv
        if result.get("category"):
            product.category = _to_str(result["category"])
        if result.get("reference"):
            product.reference = _to_str(result["reference"])
        if result.get("brand"):
            product.brand = _to_str(result["brand"])

        product.processed_data = extractor._make_json_serializable(result)
        product.status = "draft"
        db.commit()
        db.refresh(product)

    doc = db.get(Document, product.document_id)
    return {"regenerated": result, "product": product_to_out(product, doc.filename if doc else "")}


@router.post("/{product_id}/regenerate-field")
async def regenerate_field(product_id: UUID, req: RegenerateFieldRequest, db: Session = Depends(get_db)):
    product = db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    from ecoia.core.llm_factory import LLMFactory
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.output_parsers import StrOutputParser

    raw_data_str = json.dumps(product.raw_data or {}, default=str, ensure_ascii=False)
    current_processed = json.dumps(product.processed_data or {}, default=str, ensure_ascii=False)

    product_context = f"""Nom: {product.name or ''}
Description: {product.description or ''}
Prix: {product.price or ''}
Catégorie: {product.category or ''}
Référence: {product.reference or ''}
Marque: {product.brand or ''}"""

    field_instruction = f"Champ: {req.field_name} ({req.field_type})"
    if req.field_label:
        field_instruction += f" — {req.field_label}"
    if req.ai_instruction:
        field_instruction += f"\nInstruction du format: {req.ai_instruction}"
    if req.ai_hint:
        field_instruction += f"\nIndication utilisateur: {req.ai_hint}"

    llm = LLMFactory.get_llm(provider=req.provider, model_name=req.model_name, temperature=0)
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """Tu es un expert en génération de fiches produits e-commerce.
On te demande de générer la valeur d'UN SEUL champ pour un produit.

RÈGLES:
1. Retourne UNIQUEMENT la valeur du champ demandé, rien d'autre.
2. Pas de JSON, pas de guillemets autour, juste la valeur brute.
3. Utilise les données source et le contexte produit pour générer une valeur pertinente.
4. Si une indication utilisateur est fournie, suis-la en priorité.
5. NE JAMAIS INVENTER d'URL, d'image ou de certification.
6. Pour les champs numériques, retourne uniquement le nombre.""",
            ),
            (
                "human",
                """Contexte produit:
{product_context}

Données source:
{raw_data}

Données traitées existantes:
{processed_data}

{field_instruction}

Génère la valeur pour ce champ:""",
            ),
        ]
    )

    chain = prompt | llm | StrOutputParser()
    result = await chain.ainvoke(
        {
            "product_context": product_context,
            "raw_data": raw_data_str[:6000],
            "processed_data": current_processed[:2000],
            "field_instruction": field_instruction,
        }
    )

    value = result.strip().strip('"').strip("'")

    if req.field_type in ("float", "integer"):
        import re as _re

        clean = _re.sub(r"[^\d.,]", "", value).replace(",", ".")
        try:
            value = float(clean) if req.field_type == "float" else int(float(clean))
        except (ValueError, TypeError):
            pass
    elif req.field_type == "boolean":
        value = value.lower() in ("true", "oui", "yes", "1")

    return {"field_name": req.field_name, "value": value}


# ---------- Internal helpers ----------


def _build_fields_spec(format_config):
    fields_lines = []
    defaults = {}
    consts = {}

    if format_config:
        fields_raw = format_config.get("fields", {})
        field_list = []
        if isinstance(fields_raw, list):
            field_list = [f for f in fields_raw if isinstance(f, dict) and not f.get("exclude_from_extraction")]
        elif isinstance(fields_raw, dict):
            field_list = [{"name": k, **v} for k, v in fields_raw.items()]

        for f in field_list:
            fname = f.get("name", "")
            if not fname:
                continue
            ftype = f.get("type", "string")
            fdesc = f.get("description") or f.get("label") or ""
            ai_instr = f.get("ai_instruction", "")
            is_const = f.get("const", False)
            default_val = f.get("default")

            if is_const and default_val is not None:
                consts[fname] = default_val
                continue
            if default_val is not None:
                defaults[fname] = default_val

            line = f"- {fname} ({ftype}): {fdesc}"
            if ai_instr:
                line += f" [IA: {ai_instr}]"
            if f.get("required"):
                line += " [OBLIGATOIRE]"
            fields_lines.append(line)

            sub_fields = f.get("fields", [])
            if isinstance(sub_fields, list):
                for sf in sub_fields:
                    sfname = sf.get("name", "")
                    if not sfname:
                        continue
                    flat_key = f"{fname}_{sfname}"
                    sf_default = sf.get("default")
                    if sf_default is not None:
                        defaults[flat_key] = sf_default
                    line2 = f"  - {flat_key} ({sf.get('type', 'string')}): {sf.get('description') or ''}"
                    if sf.get("ai_instruction"):
                        line2 += f" [IA: {sf['ai_instruction']}]"
                    fields_lines.append(line2)

    if not fields_lines:
        fields_lines = [
            "- name (string): Nom du produit [OBLIGATOIRE]",
            "- description (string): Description détaillée du produit [OBLIGATOIRE]",
            "- description_short (string): Résumé marketing accrocheur de 1-2 phrases [IA: Génère à partir du nom et description]",
            "- price (float): Prix du produit",
            "- category (string): Catégorie du produit (ex: 'Éclairage > Ampoules')",
            "- reference (string): Référence / SKU / EAN",
            "- brand (string): Marque / Fabricant",
            "- meta_title (string): Titre SEO optimisé < 70 caractères [IA: Génère à partir du nom]",
            "- meta_description (string): Description SEO attractive < 160 caractères [IA: Génère à partir de la description]",
        ]

    return fields_lines, defaults, consts


def _to_str(v):
    if v is None:
        return None
    if isinstance(v, dict):
        return " | ".join(str(x) for x in v.values() if x)
    if isinstance(v, list):
        return ", ".join(str(x) for x in v if x)
    return str(v)


def _to_float(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, dict):
        v = v.get("value") or v.get("amount") or v.get("price") or next(iter(v.values()), None)
    if isinstance(v, str):
        import re

        clean = re.sub(r"[^\d.,]", "", v).replace(",", ".")
        try:
            return float(clean)
        except ValueError:
            return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def _flatten_result(result: dict) -> dict:
    return {k: _to_str(v) if isinstance(v, (dict, list)) else v for k, v in result.items()}
