from ecoia.services.source_preprocessor_service import InMemoryTabularParser, SourcePreprocessorService


def test_in_memory_tabular_parser_builds_tabular_doc():
    parser = InMemoryTabularParser(
        {
            "master": [
                ["name", "price"],
                ["Produit A", "10.5"],
                ["Produit B", "12.0"],
            ]
        },
        metadata={"source": "test"},
    )

    parsed = parser.parse("memory://test")

    assert parsed["type"] == "tabular_doc"
    assert "master" in parsed["sheets"]
    rows = parser.get_all_rows("memory://test", "master")
    assert rows[0][0] == "name"
    assert rows[1][0] == "Produit A"


def test_preprocess_website_manual_filters_domain_and_requires_name(monkeypatch):
    service = SourcePreprocessorService()

    def _fake_fetch(url):
        return "<html><body><h1>Produit test</h1><p>Desc</p></body></html>"

    def _fake_extract(**kwargs):
        url = kwargs["url"]
        if "without-name" in url:
            return {"name": "", "description": "x", "price": "9.9", "reference": None, "brand": None, "category": None}
        return {
            "name": "Produit test",
            "description": "Description",
            "price": "9.9",
            "reference": "REF-1",
            "brand": "BrandX",
            "category": "Cat",
        }

    monkeypatch.setattr(service, "_fetch_url", _fake_fetch)
    monkeypatch.setattr(service, "_extract_product_from_html", _fake_extract)

    result = service.preprocess_website(
        start_url="https://example.com",
        crawl_mode="manual",
        urls=[
            "https://example.com/product-1",
            "https://other.com/product-x",
            "https://example.com/without-name",
        ],
        max_pages=10,
        max_depth=1,
    )

    parsed = result.parsed
    rows = result.parser.get_all_rows("https://example.com", "master")

    # header + 1 valid row only (external domain filtered, name-less row skipped)
    assert parsed["type"] == "tabular_doc"
    assert len(rows) == 2
    assert rows[1][0] == "Produit test"
    assert rows[1][-1] == "https://example.com/product-1"


def test_preprocess_presented_catalog_vision_uses_llm_rows(monkeypatch):
    service = SourcePreprocessorService()

    monkeypatch.setattr(service, "_extract_text_best_effort", lambda _path: "Produit A | 10.5")
    monkeypatch.setattr(
        service,
        "_rows_from_unstructured_text_with_llm",
        lambda **kwargs: [["name", "price"], ["Produit A", "10.5"]],
    )

    result = service.preprocess_presented_catalog(
        file_path="dummy.pdf",
        mode="vision_model",
        provider="openai",
        model_name="gpt-4o-mini",
    )

    rows = result.parser.get_all_rows("dummy.pdf", "master")
    assert rows[0] == ["name", "price"]
    assert rows[1][0] == "Produit A"
