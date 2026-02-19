from fastapi.testclient import TestClient

from ecoia.main import app

client = TestClient(app)


def test_classification_endpoint_with_ai_output():
    payload = {
        "product_title": "Spatule en inox",
        "product_description": "Spatule de cuisine",
        "categories": [
            {
                "name": "Maison",
                "children": [
                    {
                        "name": "Cuisine",
                        "children": [{"name": "Ustensiles", "children": []}],
                    }
                ],
            }
        ],
        "ai_output": {
            "category_path": ["Maison", "Cuisine", "Ustensiles"],
            "confidence": 0.7,
        },
    }

    response = client.post("/api/v1/classification/classify", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["category_path"] == ["Maison", "Cuisine", "Ustensiles"]
    assert data["confidence"] == 0.7
    assert data["needs_review"] is False


def test_classification_endpoint_fallback():
    payload = {
        "product_title": "Spatule en inox",
        "product_description": "Spatule de cuisine",
        "categories": [
            {
                "name": "Maison",
                "children": [
                    {
                        "name": "Cuisine",
                        "children": [{"name": "Ustensiles", "children": []}],
                    }
                ],
            }
        ],
        "confidence_threshold": 0.9,
        "ai_output": {
            "category_path": ["Maison", "Cuisine", "Ustensiles"],
            "confidence": 0.7,
        },
    }

    response = client.post("/api/v1/classification/classify", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["needs_review"] is True
    assert data["reason"] == "confidence_below_threshold"


def test_classification_endpoint_invalid_path():
    payload = {
        "product_title": "Spatule en inox",
        "product_description": "Spatule de cuisine",
        "categories": [
            {
                "name": "Maison",
                "children": [
                    {
                        "name": "Cuisine",
                        "children": [{"name": "Ustensiles", "children": []}],
                    }
                ],
            }
        ],
        "ai_output": {
            "category_path": ["Maison", "Inexistant"],
            "confidence": 0.7,
        },
    }

    response = client.post("/api/v1/classification/classify", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["needs_review"] is True
    assert data["reason"] == "invalid_category_path"
