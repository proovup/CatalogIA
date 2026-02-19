import json
import re
from collections import Counter
from typing import Any, Dict, Optional

from ecoia.services.field_mapping import is_generic_column


class SheetAnalyzer:
    async def analyze(
        self,
        file_path: str,
        parser=None,
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        if parser is None:
            from ecoia.parsers import ParserFactory

            parser = ParserFactory.get_parser(file_path)

        parsed = parser.parse(file_path)
        sheets = parsed.get("sheets", {})
        if not sheets:
            return {"error": "No sheets found"}

        sheets_summary = {}
        for sn, info in sheets.items():
            rows = parser.get_all_rows(file_path, sn)
            total = len(rows) - 1 if rows else 0
            sample_rows = rows[1:21] if rows and len(rows) > 1 else []
            sheets_summary[sn] = {
                "columns": [str(c) if c is not None else None for c in info.get("columns", [])],
                "sample_rows": [[str(v) if v is not None else None for v in r] for r in sample_rows],
                "total_rows": total,
            }

        analysis = await self._llm_analyze(sheets_summary, sheets, provider, model_name)
        if analysis:
            for s in analysis.get("sheets", []):
                sn = s.get("name", "")
                if sn in sheets_summary:
                    s["total_rows"] = sheets_summary[sn]["total_rows"]
                    s["columns"] = sheets_summary[sn]["columns"]
                    s["sample_rows"] = sheets_summary[sn]["sample_rows"]
            return analysis

        return self._heuristic_analyze(sheets, sheets_summary, parser, file_path)

    async def _llm_analyze(
        self,
        sheets_summary: Dict[str, Any],
        sheets: Dict[str, Any],
        provider: Optional[str],
        model_name: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        from ecoia.core.llm_factory import LLMFactory
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_core.output_parsers import StrOutputParser

        llm = LLMFactory.get_llm(provider=provider, model_name=model_name, temperature=0)

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """Tu es un expert en analyse de structure de donnees tabulaires.
On te donne un fichier avec plusieurs feuilles/tables. Analyse les colonnes et les donnees d'exemple pour comprendre:
1. Quelle feuille est la feuille MAITRE (celle qui definit les entites/produits principaux)
2. Quelles colonnes servent de CLE DE LIAISON entre les feuilles (references, codes, identifiants)
3. Le ROLE de chaque feuille secondaire (logistique, media, technique, reglementaire, etc.)
4. Le type de RELATION: "1:1" (une ligne liee par produit) ou "1:N" (plusieurs lignes liees par produit)

Voici les feuilles disponibles:
{sheets_summary}

REGLES CRITIQUES pour les colonnes de liaison (join_columns / join_on):
- Les colonnes de liaison sont UNIQUEMENT des identifiants techniques: codes, references, SKU, EAN, GTIN, ID numeriques ou alphanumeriques courts
- Exemples de BONS identifiants: REFCIALE, CODE_ART, SKU, EAN13, GTIN, REF, ID, ARTICLE_ID, PRODUCT_CODE
- JAMAIS utiliser comme colonne de liaison:
  * Les noms/libelles (nom, name, libelle, titre, designation, description)
  * Les marques (marque, brand, fabricant, fournisseur)
  * Les prix (prix, price, tarif, montant)
  * Les categories (categorie, category, famille, gamme, type)
  * Les unites (unite, unit, conditionnement)
  * Les colonnes descriptives ou texte libre
- Une colonne de liaison doit avoir des valeurs UNIQUES ou quasi-uniques dans la feuille maitre
- Privilegie les colonnes presentes dans TOUTES ou la plupart des feuilles

Autres regles:
- La feuille maitre est celle qui contient UNE ligne par entite/produit avec les infos principales (nom, prix, description...)
- Ignore les feuilles de metadata/cartouche (parametres generaux, 1-2 lignes)
- Pour determiner 1:N, regarde si le nombre de lignes d'une feuille secondaire est tres superieur au nombre de produits

Retourne UNIQUEMENT un JSON valide:
{{
  "master_sheet": "nom_de_la_feuille_maitre",
  "join_columns": ["colonne1", "colonne2"],
  "sheets": [
    {{
      "name": "nom_feuille",
      "role": "master|logistique|media|technique|reglementaire|config|metadata",
      "relation": "master|1:1|1:N",
      "join_on": "nom_colonne_de_liaison_dans_cette_feuille",
      "description": "courte description du contenu"
    }}
  ]
}}""",
                ),
                ("human", "Analyse ce fichier et retourne le JSON d'analyse."),
            ]
        )

        for attempt in range(3):
            try:
                chain = prompt | llm | StrOutputParser()
                response = await chain.ainvoke(
                    {"sheets_summary": json.dumps(sheets_summary, default=str, ensure_ascii=False)}
                )
                json_match = re.search(r"\{.*\}", response, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                    if "master_sheet" in result and "sheets" in result:
                        if result["master_sheet"] not in sheets:
                            candidates = [s for s in sheets if s != result["master_sheet"]]
                            if candidates:
                                result["master_sheet"] = candidates[0]
                        result["join_columns"] = [c for c in result.get("join_columns", []) if not is_generic_column(c)]
                        for s in result.get("sheets", []):
                            jo = s.get("join_on", "")
                            if jo and is_generic_column(jo):
                                s["join_on"] = None
                        return result
            except Exception:
                if attempt == 2:
                    break
                continue

        return None

    def _heuristic_analyze(
        self,
        sheets: Dict[str, Any],
        sheets_summary: Dict[str, Any],
        parser,
        file_path: str,
    ) -> Dict[str, Any]:
        sheet_col_maps: Dict[str, Dict[str, int]] = {}
        for sn in sheets:
            rows = parser.get_all_rows(file_path, sn)
            if not rows:
                continue
            hdr = rows[0]
            col_map = {}
            for i, c in enumerate(hdr):
                if c is not None:
                    cl = str(c).strip().lower()
                    if cl and len(cl) < 100:
                        col_map[cl] = i
            sheet_col_maps[sn] = col_map

        cc = Counter()
        for cm in sheet_col_maps.values():
            for cn in cm:
                cc[cn] += 1
        shared = [c for c, n in cc.items() if n >= 2 and not is_generic_column(c)]

        name_keywords = {"nom", "name", "titre", "libelle", "libellé", "désignation", "designation", "produit"}
        master = None
        max_score = -1
        for sn, cm in sheet_col_maps.items():
            score = 0
            for col in cm:
                if any(k in col for k in name_keywords):
                    score += 10
            info = sheets_summary.get(sn, {})
            rows_count = info.get("total_rows", 0)
            if rows_count <= 2:
                continue
            score += min(rows_count, 1000) / 100
            if score > max_score:
                max_score = score
                master = sn

        if not master:
            master = max(sheets_summary, key=lambda s: sheets_summary[s].get("total_rows", 0))

        master_rows = sheets_summary.get(master, {}).get("total_rows", 0)

        result_sheets = []
        for sn in sheets:
            info = sheets_summary.get(sn, {})
            total = info.get("total_rows", 0)
            if sn == master:
                role, relation = "master", "master"
            elif total <= 2:
                role, relation = "metadata", "1:1"
            elif total > master_rows * 1.5:
                role, relation = "enrichment", "1:N"
            else:
                role, relation = "enrichment", "1:1"

            join_on = None
            cm = sheet_col_maps.get(sn, {})
            for col in shared:
                if col in cm:
                    join_on = col
                    break

            result_sheets.append(
                {
                    "name": sn,
                    "role": role,
                    "relation": relation,
                    "join_on": join_on,
                    "description": f"{total} lignes",
                    "total_rows": total,
                    "columns": info.get("columns", []),
                    "sample_rows": info.get("sample_rows", []),
                }
            )

        return {
            "master_sheet": master,
            "join_columns": shared,
            "sheets": result_sheets,
        }
