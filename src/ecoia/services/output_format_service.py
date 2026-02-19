import re
import yaml
from typing import Any, Dict, List
from ecoia.schemas.output_format import OutputFormatConfig, OutputField


class OutputFormatService:
    """Service for loading, validating and processing custom output formats"""

    @staticmethod
    def _slugify(value: str) -> str:
        value = value.lower().strip()
        value = re.sub(r"[^a-z0-9\s-]", "", value)
        value = re.sub(r"[\s_-]+", "-", value)
        return value.strip("-")

    @staticmethod
    def load_config(yaml_content: str) -> OutputFormatConfig:
        """Load and validate a YAML configuration"""
        try:
            config_dict = yaml.safe_load(yaml_content)
            return OutputFormatConfig(**config_dict)
        except Exception as e:
            raise ValueError(f"Invalid output format configuration: {str(e)}")

    @staticmethod
    def load_config_from_file(file_path: str) -> OutputFormatConfig:
        """Load and validate a YAML configuration from a file"""
        with open(file_path, "r", encoding="utf-8") as f:
            return OutputFormatService.load_config(f.read())

    def generate_system_prompt(self, config: OutputFormatConfig) -> str:
        """Generate AI system instructions based on the configuration"""
        prompt = [
            f"Tu es un expert en extraction de données pour {config.target_entity}.",
            "Ta mission est d'extraire les informations du document",
            "fourni et de les structurer selon le schéma JSON strict ci-dessous." "Règles d'extraction :",
            "- Ne fournis que le JSON brut, sans texte avant ou après.",
            "- Respecte scrupuleusement les types de données demandés.",
            "- Si un champ est marqué comme 'required' et absent, ",
            "essaie de le déduire ou laisse une valeur cohérente selon sa description.",
            "\nSchéma attendu :",
        ]

        schema_desc = self._build_schema_description(config.fields)
        prompt.append(schema_desc)

        # Add specific AI instructions from fields
        specific_instructions = self._collect_ai_instructions(config.fields)
        if specific_instructions:
            prompt.append("\nConsignes spécifiques par champ :")
            prompt.extend(specific_instructions)

        if config.processing.translate_to:
            prompt.append(
                f"\nNote : Toutes les valeurs textuelles doivent être traduites en {config.processing.translate_to}."
            )

        return "\n".join(prompt)

    def _build_schema_description(self, fields: List[OutputField], indent: int = 0) -> str:
        """Recursively build a description of the JSON schema"""
        lines = []
        spacer = "  " * indent
        for field in fields:
            # Skip fields that should not be extracted by AI
            if field.exclude_from_extraction or field.ai_instruction:
                continue

            desc = f"{spacer}- {field.name} ({field.type})"
            if field.description:
                desc += f": {field.description}"
            if field.required:
                desc += " [REQUIS]"
            if field.const:
                desc += f" [VALEUR FIXE: {field.default}]"
            lines.append(desc)

            if field.fields:
                lines.append(self._build_schema_description(field.fields, indent + 1))
        return "\n".join(lines)

    def _collect_ai_instructions(self, fields: List[OutputField], prefix: str = "") -> List[str]:
        """Collect all specific AI instructions from fields"""
        instructions = []
        for field in fields:
            # Skip fields that should not be extracted by AI
            if field.exclude_from_extraction or field.ai_instruction:
                continue

            field_path = f"{prefix}{field.name}"
            # Only include instructions for fields that are extracted and have ai_instruction
            # (But if they have ai_instruction, they are excluded above)
            # So this section will never be reached for fields with ai_instruction
            if field.ai_instruction:
                instructions.append(f"- {field_path}: {field.ai_instruction}")
            if field.fields:
                instructions.extend(self._collect_ai_instructions(field.fields, f"{field_path}."))
        return instructions

    def apply_transformations(self, data: Dict[str, Any], config: OutputFormatConfig) -> Dict[str, Any]:
        """Apply post-processing transformations and validations to extracted data"""
        processed_data = data.copy()
        self._process_fields(processed_data, config.fields)
        errors = self.validate_output(processed_data, config)
        if errors:
            raise ValueError(f"Output validation failed: {', '.join(errors)}")
        return processed_data

    def validate_output(self, data: Dict[str, Any], config: OutputFormatConfig) -> List[str]:
        """Validate extracted data against the output format configuration"""
        errors: List[str] = []
        for field in config.fields:
            self._validate_field(data, field, field.name, errors)
        return errors

    def _process_fields(self, data: Dict[str, Any], fields: List[OutputField]):
        """Recursively process transformations, mappings and calculations"""
        for field in fields:
            # 1. Handle fields excluded from extraction
            if field.exclude_from_extraction or field.ai_instruction:
                # For excluded fields, use default value or const
                if field.const:
                    data[field.name] = field.default
                elif field.default is not None:
                    data[field.name] = field.default
                else:
                    # Add the field even if no default (for ai_instruction fields)
                    if field.name not in data:
                        data[field.name] = None
                # If field is an object with sub-fields, process them recursively
                if field.type == "object" and field.fields:
                    if field.name not in data:
                        data[field.name] = {}
                    self._process_fields(data[field.name], field.fields)
                continue

            # 2. Handle Constant values
            if field.const:
                data[field.name] = field.default
                continue

            # 3. Skip if missing and not required (or handled by default)
            if field.name not in data or data[field.name] is None:
                if field.default is not None:
                    data[field.name] = field.default
                continue

            value = data[field.name]

            # 4. Handle Nested Objects
            if field.type == "object" and field.fields and isinstance(value, dict):
                self._process_fields(value, field.fields)

            # 5. Handle Arrays
            elif field.type == "array" and isinstance(value, list):
                pass

            # 6. Handle Mappings (Enums)
            if field.mapping and value in field.mapping:
                value = field.mapping[value]
            elif field.options and value not in field.options:
                # If value not in options, keep original or set to default?
                # For now, keep original but this could be a validation error
                pass

            # 7. Apply Transformations
            if field.transform:
                for t in field.transform:
                    value = self._apply_transform(value, t)

            data[field.name] = value

        # 8. Handle Calculations (after all individual fields are processed)
        for field in fields:
            if field.calculation and not field.exclude_from_extraction and not field.ai_instruction:
                data[field.name] = self._evaluate_calculation(data, field.calculation)

    def _validate_field(
        self,
        data: Dict[str, Any],
        field: OutputField,
        field_path: str,
        errors: List[str],
    ) -> None:
        # Skip validation for fields excluded from extraction that have default/const values
        if (field.exclude_from_extraction or field.ai_instruction) and (field.default is not None or field.const):
            return

        if field.name not in data or data[field.name] is None:
            if field.required and not field.exclude_from_extraction and not field.ai_instruction:
                errors.append(f"{field_path} is required")
            return

        value = data[field.name]
        if not self._validate_type(value, field):
            errors.append(f"{field_path} has invalid type, expected {field.type}")
            return

        if field.type == "object" and field.fields and isinstance(value, dict):
            for child in field.fields:
                self._validate_field(value, child, f"{field_path}.{child.name}", errors)
            return

        if field.type == "array" and isinstance(value, list) and field.item_type:
            for idx, item in enumerate(value):
                if not self._validate_primitive_type(item, field.item_type):
                    errors.append(f"{field_path}[{idx}] has invalid type, expected {field.item_type}")

        if field.options and value not in field.options:
            errors.append(f"{field_path} must be one of {field.options}")

        if field.validation:
            self._validate_constraints(value, field, field_path, errors)

    def _validate_type(self, value: Any, field: OutputField) -> bool:
        if field.type == "string" or field.type == "html" or field.type == "date":
            return isinstance(value, str)
        if field.type == "integer":
            return isinstance(value, int) and not isinstance(value, bool)
        if field.type == "float":
            return isinstance(value, (int, float)) and not isinstance(value, bool)
        if field.type == "boolean":
            return isinstance(value, bool)
        if field.type == "enum":
            return isinstance(value, str)
        if field.type == "object":
            return isinstance(value, dict)
        if field.type == "array":
            return isinstance(value, list)
        return True

    def _validate_primitive_type(self, value: Any, field_type: str) -> bool:
        temp_field = OutputField(name="item", type=field_type)
        return self._validate_type(value, temp_field)

    def _validate_constraints(
        self,
        value: Any,
        field: OutputField,
        field_path: str,
        errors: List[str],
    ) -> None:
        validation = field.validation
        if not validation:
            return

        if isinstance(value, str):
            if validation.max_length is not None and len(value) > validation.max_length:
                errors.append(f"{field_path} exceeds max_length {validation.max_length}")
            if validation.min_length is not None and len(value) < validation.min_length:
                errors.append(f"{field_path} below min_length {validation.min_length}")
            if validation.pattern and not re.match(validation.pattern, value):
                errors.append(validation.message or f"{field_path} does not match pattern")

        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            min_value = validation.min_value if validation.min_value is not None else validation.min
            if min_value is not None and value < min_value:
                errors.append(f"{field_path} below min_value {min_value}")
            if validation.max_value is not None and value > validation.max_value:
                errors.append(f"{field_path} exceeds max_value {validation.max_value}")

    def _apply_transform(self, value: Any, transform_name: str) -> Any:
        """Apply a single transformation by name"""
        if value is None:
            return None

        t = transform_name.lower()
        if t == "trim" and isinstance(value, str):
            return value.strip()
        elif t == "uppercase" and isinstance(value, str):
            return value.upper()
        elif t == "lowercase" and isinstance(value, str):
            return value.lower()
        elif t == "capitalize" and isinstance(value, str):
            return value.capitalize()
        elif t == "slugify" and isinstance(value, str):
            return self._slugify(value)
        elif t == "clean_html_tags" and isinstance(value, str):
            return re.sub("<[^<]+?>", "", value)

        return value

    def _evaluate_calculation(self, data: Dict[str, Any], expression: str) -> Any:
        """Basic expression evaluation for calculated fields"""
        # Security: extremely limited eval or simple parser
        # For POC, let's support basic arithmetic between fields
        try:
            # Replace field names with values
            # This is a very naive implementation, should be improved for production
            for key, val in data.items():
                if isinstance(val, (int, float)):
                    expression = expression.replace(key, str(val))

            # Only allow basic arithmetic characters
            if not re.match(r"^[0-9\.\+\-\*\/\(\)\s]+$", expression):
                return None

            return eval(expression, {"__builtins__": {}}, {})
        except Exception:
            return None
