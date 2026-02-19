import pytest

from ecoia.schemas.classification import CategoryNode, ClassificationRequest
from ecoia.services.classification_service import ClassificationService


@pytest.fixture
def category_tree():
    return [
        CategoryNode(
            name="Maison",
            children=[
                CategoryNode(
                    name="Cuisine",
                    children=[CategoryNode(name="Ustensiles")],
                )
            ],
        )
    ]


@pytest.mark.asyncio
async def test_classify_valid_output(category_tree):
    service = ClassificationService()
    request = ClassificationRequest(
        product_title="Spatule en inox",
        product_description="Spatule de cuisine",
        categories=category_tree,
        ai_output={
            "category_path": ["Maison", "Cuisine", "Ustensiles"],
            "confidence": 0.8,
        },
    )

    result = await service.classify(request)

    assert result.category_path == ["Maison", "Cuisine", "Ustensiles"]
    assert result.confidence == 0.8
    assert result.needs_review is False


@pytest.mark.asyncio
async def test_classify_fallback(category_tree):
    service = ClassificationService()
    request = ClassificationRequest(
        product_title="Spatule en inox",
        product_description="Spatule de cuisine",
        categories=category_tree,
        confidence_threshold=0.9,
        ai_output={
            "category_path": ["Maison", "Cuisine", "Ustensiles"],
            "confidence": 0.4,
        },
    )

    result = await service.classify(request)

    assert result.needs_review is True
    assert result.reason == "confidence_below_threshold"


@pytest.mark.asyncio
async def test_invalid_category_path(category_tree):
    service = ClassificationService()
    request = ClassificationRequest(
        product_title="Spatule en inox",
        product_description="Spatule de cuisine",
        categories=category_tree,
        ai_output={"category_path": ["Maison", "Salon"], "confidence": 0.6},
    )

    result = await service.classify(request)
    assert result.needs_review is True
    assert result.reason == "invalid_category_path"
