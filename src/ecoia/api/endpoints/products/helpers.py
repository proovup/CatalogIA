from typing import Optional
from ecoia.db.models import Product


def product_to_out(product: Product, doc_filename: str = "", supplier_name: str = "") -> dict:
    return {
        "id": str(product.id),
        "document_id": str(product.document_id),
        "supplier_id": str(product.supplier_id) if product.supplier_id else None,
        "supplier_name": supplier_name,
        "name": product.name,
        "description": product.description,
        "price": product.price,
        "category": product.category,
        "reference": product.reference,
        "brand": product.brand,
        "status": product.status,
        "raw_data": product.raw_data,
        "processed_data": product.processed_data,
        "created_at": product.created_at.isoformat() if product.created_at else None,
        "updated_at": product.updated_at.isoformat() if product.updated_at else None,
        "document_filename": doc_filename,
    }


def get_product_identifier(product: Product) -> Optional[str]:
    if product.reference and str(product.reference).strip():
        return str(product.reference).strip().lower()
    if product.raw_data and isinstance(product.raw_data, dict):
        mapped = product.raw_data.get("mapped_fields", {})
        for key in ["ean", "ean13", "gtin", "upc", "sku", "reference", "ref", "code_produit"]:
            val = mapped.get(key)
            if val and str(val).strip():
                return str(val).strip().lower()
    return None


def auto_map_basic_fields(columns) -> dict:
    mapping = {}
    name_kw = [
        "nom",
        "name",
        "titre",
        "title",
        "désignation",
        "designation",
        "libellé",
        "libelle",
        "produit",
        "article",
    ]
    desc_kw = ["description", "desc", "détail", "detail", "commentaire"]
    price_kw = ["prix", "price", "tarif", "montant", "cost", "coût", "ppc", "pvp", "ht", "ttc"]
    ref_kw = [
        "reference",
        "ref",
        "référence",
        "réf",
        "sku",
        "ean",
        "ean13",
        "gtin",
        "upc",
        "code",
        "code_produit",
        "article_number",
        "numéro",
    ]
    brand_kw = ["marque", "brand", "fabricant", "manufacturer"]
    cat_kw = ["catégorie", "categorie", "category", "famille", "rayon", "gamme", "type"]

    columns_lower = [str(c).strip().lower() if c else "" for c in columns]

    for i, col in enumerate(columns_lower):
        if not col:
            continue
        if not mapping.get("name") and any(k in col for k in name_kw):
            mapping["name"] = i
        elif not mapping.get("description") and any(k in col for k in desc_kw):
            mapping["description"] = i
        elif not mapping.get("price") and any(k in col for k in price_kw):
            mapping["price"] = i
        elif not mapping.get("reference") and any(k in col for k in ref_kw):
            mapping["reference"] = i
        elif not mapping.get("brand") and any(k in col for k in brand_kw):
            mapping["brand"] = i
        elif not mapping.get("category") and any(k in col for k in cat_kw):
            mapping["category"] = i

    return mapping
