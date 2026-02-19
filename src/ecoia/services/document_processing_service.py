import json
from typing import Any, Dict, Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser

from ecoia.parsers import ParserFactory
from ecoia.schemas.output_format import OutputFormatConfig
from ecoia.services.output_format_service import OutputFormatService
from ecoia.core.llm_factory import LLMFactory


class DocumentProcessingService:
    """Orchestrates parsing + output format handling."""

    def __init__(self):
        self.output_format_service = OutputFormatService()

    def load_output_config(self, config_path: str) -> OutputFormatConfig:
        return self.output_format_service.load_config_from_file(config_path)

    def build_prompt(self, config: OutputFormatConfig) -> str:
        return self.output_format_service.generate_system_prompt(config)

    def parse_document(self, file_path: str) -> Dict[str, Any]:
        parser = ParserFactory.get_parser(file_path)
        return parser.parse(file_path)

    async def process_document(
        self,
        file_path: str,
        config_path: str,
        ai_output: Optional[Dict[str, Any]] = None,
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        config = self.load_output_config(config_path)
        parsed = self.parse_document(file_path)
        prompt_text = self.build_prompt(config)

        if parsed.get("type") == "excel":
            return await self._process_excel(file_path, config, provider, model_name)

        if ai_output is None:
            # Call LLM to get extraction
            llm = LLMFactory.get_llm(provider=provider, model_name=model_name, temperature=0)
            prompt = ChatPromptTemplate.from_messages(
                [
                    ("system", "You are a helpful assistant that extracts structured data from documents."),
                    ("human", "{instructions}\n\nDocument content:\n{content}\n\nJSON Output:"),
                ]
            )
            chain = prompt | llm | JsonOutputParser()

            content = parsed.get("text", "") or str(parsed)
            ai_output = await chain.ainvoke({"instructions": prompt_text, "content": content})

        processed_output = self.output_format_service.apply_transformations(ai_output, config)

        return {
            "config": config.model_dump(),
            "parsed": parsed,
            "prompt": prompt_text,
            "output": processed_output,
        }

    async def _process_excel_mapping(
        self,
        parsed_data: Dict[str, Any],
        config: OutputFormatConfig,
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get column mapping from AI for Excel files, identifying ALL relevant sheets."""
        llm = LLMFactory.get_llm(provider=provider, model_name=model_name, temperature=0)

        # Prepare sheet summary for LLM
        sheets_summary = {}
        for name, info in parsed_data.get("sheets", {}).items():
            sheets_summary[name] = {"columns": info["columns"], "samples": info["samples"]}

        mapping_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    """Tu es un expert en analyse de données Excel.
On me demande d'extraire des entités de type: {target_entity}
Voici les champs requis (certains peuvent être des objets avec des sous-champs): {fields}

Voici un résumé des feuilles Excel disponibles (colonnes et exemples):
{sheets_summary}

Instructions:
1. Identifie TOUTES les feuilles pertinentes pour l'extraction (feuille principale + feuilles complémentaires).
2. La feuille principale (primary_sheet) est celle qui contient les lignes produit.
3. Les feuilles complémentaires (secondary_sheets) contiennent des données supplémentaires
   liées par des identifiants communs (EAN, SKU, référence, etc.).
4. Pour chaque feuille pertinente, fournis le mapping des colonnes (0-indexed).
5. Identifie les colonnes de liaison (join_columns) entre les feuilles.
6. L'index DOIT être un entier (integer). Si une colonne n'est pas trouvée, utilise null.
7. Si un champ est un objet, mappe ses sous-champs individuellement.
8. Retourne UNIQUEMENT un JSON valide sous ce format sans aucun commentaire:
{{
  "primary_sheet": "Nom de la feuille principale",
  "column_mapping": {{"nom_du_champ": 0, ...}},
  "secondary_sheets": [
    {{
      "sheet_name": "Nom feuille complémentaire",
      "column_mapping": {{"nom_du_champ": 0, ...}},
      "join_columns": {{"colonne_feuille_principale": "colonne_cette_feuille"}}
    }}
  ]
}}
Si une seule feuille est pertinente, retourne secondary_sheets comme liste vide [].""",
                ),
                ("human", "Analyse ce fichier Excel et fournis le mapping multi-feuilles en JSON uniquement."),
            ]
        )

        # Prepare a flat list of fields and sub-fields for the prompt
        def get_flat_fields(fields, prefix=""):
            flat = []
            for f in fields:
                # Skip fields that should not be extracted by AI
                if f.exclude_from_extraction or f.ai_instruction:
                    continue

                field_key = f"{prefix}{f.name}"
                flat.append(f"{field_key} ({f.description or ''})")
                if f.fields:
                    flat.extend(get_flat_fields(f.fields, f"{field_key}."))
            return flat

        fields_desc = get_flat_fields(config.fields)

        # Use a more robust approach for JSON parsing
        import re

        # Try to get clean JSON from AI
        for attempt in range(3):
            try:
                chain = mapping_prompt | llm | StrOutputParser()

                response = await chain.ainvoke(
                    {
                        "target_entity": config.target_entity,
                        "fields": ", ".join(fields_desc),
                        "sheets_summary": json.dumps(sheets_summary, default=str),
                    }
                )

                # Extract JSON from response
                json_match = re.search(r"\{.*\}", response, re.DOTALL)
                if json_match:
                    json_str = json_match.group()
                    mapping_result = json.loads(json_str)

                    # Handle new multi-sheet format
                    if "primary_sheet" in mapping_result and "column_mapping" in mapping_result:
                        # Ensure secondary_sheets exists
                        mapping_result.setdefault("secondary_sheets", [])
                        return mapping_result

                    # Backward compatibility: old single-sheet format
                    if "sheet_name" in mapping_result and "column_mapping" in mapping_result:
                        return {
                            "primary_sheet": mapping_result["sheet_name"],
                            "column_mapping": mapping_result["column_mapping"],
                            "secondary_sheets": [],
                        }

            except Exception:
                if attempt == 2:
                    # Last attempt, create default mapping
                    sheets = parsed_data.get("sheets", {})
                    first_sheet = list(sheets.keys())[0] if sheets else "Sheet1"
                    return {
                        "primary_sheet": first_sheet,
                        "column_mapping": {
                            f"col_{i}": i for i in range(len(sheets.get(first_sheet, {}).get("columns", [])))
                        },
                        "secondary_sheets": [],
                    }
                continue

        # Fallback
        sheets = parsed_data.get("sheets", {})
        first_sheet = list(sheets.keys())[0] if sheets else "Sheet1"
        return {
            "primary_sheet": first_sheet,
            "column_mapping": {f"col_{i}": i for i in range(len(sheets.get(first_sheet, {}).get("columns", [])))},
            "secondary_sheets": [],
        }

    def _build_secondary_index(
        self,
        parser,
        file_path: str,
        secondary_sheet: Dict[str, Any],
    ) -> Dict[str, Dict[str, Any]]:
        """Build a lookup index from a secondary sheet keyed by join column values."""
        sheet_name = secondary_sheet.get("sheet_name", "")
        col_mapping = secondary_sheet.get("column_mapping", {})
        join_columns = secondary_sheet.get("join_columns", {})

        all_rows = parser.get_all_rows(file_path, sheet_name)
        if not all_rows or len(all_rows) < 2:
            return {}

        header_row = all_rows[0]
        data_rows = all_rows[1:]

        # Find the join column index in the secondary sheet
        # join_columns: {"primary_col_name": "secondary_col_name"}
        secondary_join_col_name = None
        for _, sec_col in join_columns.items():
            secondary_join_col_name = sec_col
            break

        if not secondary_join_col_name:
            return {}

        # Find the index of the join column in the secondary header
        header_lower = [str(c).strip().lower() if c else "" for c in header_row]
        join_col_idx = None
        for idx, col in enumerate(header_lower):
            if col == str(secondary_join_col_name).strip().lower():
                join_col_idx = idx
                break

        # If not found by name, try as integer index
        if join_col_idx is None and isinstance(secondary_join_col_name, int):
            join_col_idx = secondary_join_col_name

        if join_col_idx is None:
            return {}

        index: Dict[str, Dict[str, Any]] = {}
        for row in data_rows:
            if not row or join_col_idx >= len(row):
                continue
            key_val = row[join_col_idx]
            if key_val is None or not str(key_val).strip():
                continue
            key = str(key_val).strip()

            # Extract mapped fields from this row
            row_data = {}
            for field_name, col_idx in col_mapping.items():
                val = self._safe_get_col_value(row, col_idx)
                if val is not None:
                    row_data[field_name] = val

            # Also store full row for raw_data
            full_row = {
                str(header_row[i]) if i < len(header_row) else f"col_{i}": row[i] if i < len(row) else None
                for i in range(max(len(header_row), len(row)))
            }
            row_data["_full_row"] = full_row
            row_data["_sheet_name"] = sheet_name

            # Keep first match per key (or could accumulate)
            if key not in index:
                index[key] = row_data

        return index

    @staticmethod
    def _safe_get_col_value(row, col_idx):
        """Safely extract a column value from a row."""
        if isinstance(col_idx, int) and 0 <= col_idx < len(row):
            return row[col_idx]
        elif isinstance(col_idx, str) and col_idx.isdigit():
            idx = int(col_idx)
            if 0 <= idx < len(row):
                return row[idx]
        return None

    async def _process_excel(
        self,
        file_path: str,
        config: OutputFormatConfig,
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Specialized processing for Excel files with multi-sheet linking."""
        parser = ParserFactory.get_parser(file_path)
        parsed = parser.parse(file_path)

        # 1. Get multi-sheet mapping from AI
        mapping_result = await self._process_excel_mapping(parsed, config, provider, model_name)

        primary_sheet = mapping_result.get("primary_sheet", "")
        column_mapping = mapping_result.get("column_mapping", {})
        secondary_sheets = mapping_result.get("secondary_sheets", [])

        # 2. Extract primary sheet rows
        all_rows = parser.get_all_rows(file_path, primary_sheet)
        if not all_rows:
            return {"error": f"Sheet {primary_sheet} not found or empty"}

        header_row = all_rows[0]
        data_rows = all_rows[1:]

        # 3. Build secondary sheet indexes for cross-sheet merging
        secondary_indexes: list[tuple[Dict[str, Any], Dict[str, Dict[str, Any]]]] = []
        for sec_sheet in secondary_sheets:
            sec_index = self._build_secondary_index(parser, file_path, sec_sheet)
            if sec_index:
                secondary_indexes.append((sec_sheet, sec_index))

        # Determine the join column index in the primary sheet for each secondary
        primary_join_indices: list[tuple[int | None, Dict[str, Any], Dict[str, Dict[str, Any]]]] = []
        header_lower = [str(c).strip().lower() if c else "" for c in header_row]
        for sec_sheet, sec_index in secondary_indexes:
            join_columns = sec_sheet.get("join_columns", {})
            primary_col_name = None
            for prim_col, _ in join_columns.items():
                primary_col_name = prim_col
                break
            if not primary_col_name:
                continue
            # Find index in primary header
            prim_join_idx = None
            for idx, col in enumerate(header_lower):
                if col == str(primary_col_name).strip().lower():
                    prim_join_idx = idx
                    break
            if prim_join_idx is None and isinstance(primary_col_name, int):
                prim_join_idx = primary_col_name
            primary_join_indices.append((prim_join_idx, sec_sheet, sec_index))

        def set_nested_value(d, keys, value):
            for key in keys[:-1]:
                d = d.setdefault(key, {})
            d[keys[-1]] = value

        extracted_data = []
        for row_idx, row in enumerate(data_rows[:100]):
            item = {}

            # Map primary columns
            for field_path, col_idx in column_mapping.items():
                val = self._safe_get_col_value(row, col_idx)
                if val is not None:
                    keys = field_path.split(".")
                    set_nested_value(item, keys, val)

            # Merge data from secondary sheets
            source_sheets = [{"sheet_name": primary_sheet, "row_index": row_idx + 1}]
            for prim_join_idx, sec_sheet, sec_index in primary_join_indices:
                if prim_join_idx is None or prim_join_idx >= len(row):
                    continue
                join_val = row[prim_join_idx]
                if join_val is None or not str(join_val).strip():
                    continue
                key = str(join_val).strip()
                linked_data = sec_index.get(key)
                if not linked_data:
                    continue

                # Merge secondary fields into item (don't overwrite existing)
                sec_col_mapping = sec_sheet.get("column_mapping", {})
                for field_path in sec_col_mapping:
                    if field_path in linked_data and field_path not in ("_full_row", "_sheet_name"):
                        keys = field_path.split(".")
                        # Only set if not already present from primary
                        current = item
                        exists = True
                        for k in keys:
                            if isinstance(current, dict) and k in current:
                                current = current[k]
                            else:
                                exists = False
                                break
                        if not exists or current is None:
                            set_nested_value(item, keys, linked_data[field_path])

                source_sheets.append(
                    {
                        "sheet_name": linked_data.get("_sheet_name", sec_sheet.get("sheet_name", "")),
                        "join_key": key,
                    }
                )

            if not item:
                continue

            # Store source sheet info for traceability
            item["_source_sheets"] = source_sheets

            try:
                processed_item = self.output_format_service.apply_transformations(item, config)
                extracted_data.append(processed_item)
            except Exception:
                extracted_data.append(item)

        return {
            "config": config.model_dump(),
            "parsed": parsed,
            "prompt": "Excel multi-sheet mapping used",
            "output": extracted_data,
            "mapping": mapping_result,
        }

    def load_ai_output(self, ai_output_path: str) -> Dict[str, Any]:
        with open(ai_output_path, "r", encoding="utf-8") as file:
            return json.load(file)
