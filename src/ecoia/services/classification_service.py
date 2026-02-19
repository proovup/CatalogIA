import json
from typing import List, Dict, Any, Optional

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from ecoia.config import settings
from ecoia.core.llm_factory import LLMFactory
from ecoia.schemas.classification import (
    CategoryNode,
    ClassificationRequest,
    ClassificationResponse,
)


class ClassificationService:
    """Service for product category classification using LLM."""

    def __init__(self, provider: Optional[str] = None, model_name: Optional[str] = None):
        self.provider = provider
        self.model_name = model_name

    def build_prompt(self, categories: List[CategoryNode]) -> str:
        category_lines = self._format_categories(categories)
        return "\n".join(
            [
                "Tu es un expert en classification produit pour un site e-commerce.",
                "Analyse le titre et la description du produit fournis et retourne un JSON strict.",
                "",
                "### Format de Sortie Attendu",
                '{{"category_path": ["Parent", "Enfant", "Petit-Enfant"], "confidence": 0.82}}',
                "",
                "### Règles",
                "- category_path doit être un tableau de chaînes représentant le chemin complet dans l'arbre.",
                "- category_path DOIT correspondre à un chemin existant dans l'arbre fourni.",
                "- confidence est un nombre flottant entre 0 et 1.",
                "",
                "### Exemples (Few-Shot)",
                "Produit: Spatule en silicone, Ustensile de cuisine résistant à la chaleur.",
                'Réponse: {{"category_path": ["Maison", "Cuisine", "Ustensiles"], "confidence": 0.95}}',
                "",
                "Produit: Ampoule LED E27, Ampoule basse consommation 10W.",
                'Réponse: {{"category_path": ["Maison", "Éclairage", "Ampoules"], "confidence": 0.98}}',
                "",
                "### Arbre de catégories disponibles",
                category_lines,
                "",
                "Produit: {product_info}",
                "Réponse:",
            ]
        )

    async def classify(self, request: ClassificationRequest) -> ClassificationResponse:
        """
        Classifie un produit. Si ai_output est fourni, utilise cette sortie (utile pour le test/bypass).
        Sinon, appelle l'LLM.
        """
        if request.ai_output:
            payload = self._extract_ai_output(request.ai_output)
        else:
            payload = await self._call_llm(request)

        category_path = payload.get("category_path")
        confidence = payload.get("confidence")

        if not isinstance(category_path, list) or not all(isinstance(item, str) and item for item in category_path):
            raise ValueError("Invalid category_path format")
        if not isinstance(confidence, (int, float)):
            raise ValueError("Invalid confidence format")

        if not self._is_valid_path(request.categories, category_path):
            # Si le chemin n'est pas valide, on force un review
            return ClassificationResponse(
                category_path=category_path,
                confidence=float(confidence),
                needs_review=True,
                reason="invalid_category_path",
            )

        threshold = (
            request.confidence_threshold
            if request.confidence_threshold is not None
            else settings.CLASSIFICATION_CONFIDENCE_THRESHOLD
        )
        needs_review = float(confidence) < threshold
        reason = "confidence_below_threshold" if needs_review else None

        return ClassificationResponse(
            category_path=category_path,
            confidence=float(confidence),
            needs_review=needs_review,
            reason=reason,
        )

    async def _call_llm(self, request: ClassificationRequest) -> Dict[str, Any]:
        """Appelle l'LLM via LangChain pour obtenir la classification."""
        llm = LLMFactory.get_llm(provider=self.provider, model_name=self.model_name, temperature=0)

        prompt_text = self.build_prompt(request.categories)
        prompt = ChatPromptTemplate.from_template(prompt_text)

        chain = prompt | llm | JsonOutputParser()

        product_info = f"{request.product_title}. {request.product_description or ''}"

        try:
            result = await chain.ainvoke({"product_info": product_info})
            return result
        except Exception as e:
            # En cas d'erreur LLM, on pourrait retourner un fallback ou raise
            raise RuntimeError(f"LLM classification failed: {str(e)}")

    def _extract_ai_output(self, ai_output: Any) -> dict:
        if ai_output is None:
            raise ValueError("ai_output is required if not calling LLM")
        if isinstance(ai_output, dict):
            return ai_output
        if isinstance(ai_output, str):
            try:
                return json.loads(ai_output)
            except json.JSONDecodeError:
                raise ValueError("ai_output string is not valid JSON")
        raise ValueError("ai_output must be a dict or JSON string")

    def _is_valid_path(self, categories: List[CategoryNode], path: List[str]) -> bool:
        current_level = categories
        for segment in path:
            match = next((node for node in current_level if node.name == segment), None)
            if not match:
                return False
            current_level = match.children
        return True

    def _format_categories(self, categories: List[CategoryNode], depth: int = 0) -> str:
        lines: List[str] = []
        prefix = "  " * depth
        for node in categories:
            lines.append(f"{prefix}- {node.name}")
            if node.children:
                lines.append(self._format_categories(node.children, depth + 1))
        return "\n".join(lines)
