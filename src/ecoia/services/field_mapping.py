from typing import Any, Dict, Optional
import re
from uuid import UUID
from datetime import datetime, date, time

_PRICE_RE = re.compile(r"[^\d.,]")

FIELD_MAP: Dict[str, str] = {
    "nom": "name",
    "name": "name",
    "titre": "name",
    "title": "name",
    "désignation": "name",
    "designation": "name",
    "libellé": "name",
    "libelle": "name",
    "produit": "name",
    "article": "name",
    "description": "description",
    "desc": "description",
    "détail": "description",
    "detail": "description",
    "commentaire": "description",
    "prix": "price",
    "price": "price",
    "tarif": "price",
    "montant": "price",
    "cost": "price",
    "coût": "price",
    "ppc": "price",
    "pvp": "price",
    "catégorie": "category",
    "categorie": "category",
    "category": "category",
    "famille": "category",
    "rayon": "category",
    "gamme": "category",
    "marque": "brand",
    "brand": "brand",
    "fabricant": "brand",
    "manufacturer": "brand",
    "reference": "reference",
    "ref": "reference",
    "référence": "reference",
    "réf": "reference",
    "sku": "reference",
    "ean": "reference",
    "ean13": "reference",
    "gtin": "reference",
    "upc": "reference",
    "code": "reference",
    "code_produit": "reference",
    "numéro": "reference",
}

GENERIC_COLUMN_KEYWORDS = {
    "nom",
    "name",
    "titre",
    "title",
    "libelle",
    "libellé",
    "désignation",
    "designation",
    "produit",
    "article",
    "description",
    "desc",
    "détail",
    "detail",
    "commentaire",
    "prix",
    "price",
    "tarif",
    "montant",
    "cost",
    "coût",
    "ppc",
    "pvp",
    "catégorie",
    "categorie",
    "category",
    "famille",
    "rayon",
    "gamme",
    "type",
    "marque",
    "brand",
    "fabricant",
    "manufacturer",
    "fournisseur",
    "supplier",
    "unite",
    "unité",
    "unit",
    "conditionnement",
    "poids",
    "weight",
    "hauteur",
    "largeur",
    "longueur",
    "profondeur",
    "haut",
    "larg",
    "prof",
    "couleur",
    "color",
    "taille",
    "size",
    "matiere",
    "matière",
    "statut",
    "status",
    "actif",
    "active",
    "visible",
    "date",
    "created",
    "updated",
    "modified",
}


def is_generic_column(col_name: str) -> bool:
    cl = str(col_name).strip().lower()
    if cl in GENERIC_COLUMN_KEYWORDS:
        return True
    for kw in GENERIC_COLUMN_KEYWORDS:
        if cl == kw or cl.startswith(kw + "_") or cl.endswith("_" + kw):
            return True
    if len(cl) > 30:
        return True
    return False


def parse_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        clean = _PRICE_RE.sub("", val).replace(",", ".")
        try:
            return float(clean)
        except ValueError:
            return None
    return None


def extract_price(product_data: Dict) -> Optional[float]:
    for field in ("price", "prix", "tarif", "montant", "cost", "coût", "ppc", "pvp"):
        val = product_data.get(field)
        parsed = parse_float(val)
        if parsed is not None:
            return parsed
    return None


def json_safe(obj: Any) -> Any:
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, (datetime, date, time)):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [json_safe(v) for v in obj]
    return obj
