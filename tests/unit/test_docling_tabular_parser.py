import types
import sys

import pytest

from ecoia.parsers.docling_tabular import DoclingTabularParser


class _FakeValues:
    def __init__(self, rows):
        self._rows = rows

    def tolist(self):
        return self._rows


class _FakeDataFrame:
    def __init__(self, columns, rows):
        self.columns = columns
        self.values = _FakeValues(rows)


class _FakeTable:
    def __init__(self, columns, rows):
        self._df = _FakeDataFrame(columns, rows)

    def export_to_dataframe(self):
        return self._df


class _FakeDoc:
    def __init__(self, tables=None, markdown=""):
        self.tables = tables or []
        self.markdown = markdown


class _FakeResult:
    def __init__(self, document):
        self.document = document


def _install_fake_docling(monkeypatch, document):
    class _FakeConverter:
        def convert(self, _file_path):
            return _FakeResult(document)

    docling_pkg = types.ModuleType("docling")
    converter_mod = types.ModuleType("docling.document_converter")
    converter_mod.DocumentConverter = _FakeConverter

    monkeypatch.setitem(sys.modules, "docling", docling_pkg)
    monkeypatch.setitem(sys.modules, "docling.document_converter", converter_mod)


def test_docling_tabular_parser_returns_sheet_like_structure(monkeypatch):
    fake_doc = _FakeDoc(
        tables=[_FakeTable(["SKU", "Nom", "Prix"], [["A-001", "Produit A", "10.5"], ["A-002", "Produit B", "12.0"]])]
    )
    _install_fake_docling(monkeypatch, fake_doc)

    parser = DoclingTabularParser()
    parsed = parser.parse("dummy.pdf")

    assert parsed["type"] == "tabular_doc"
    assert "table_1" in parsed["sheets"]
    rows = parser.get_all_rows("dummy.pdf", "table_1")
    assert rows[0] == ("SKU", "Nom", "Prix")
    assert rows[1][0] == "A-001"


def test_docling_tabular_parser_raises_explicit_error_when_no_tables(monkeypatch):
    _install_fake_docling(monkeypatch, _FakeDoc(tables=[]))

    parser = DoclingTabularParser()
    with pytest.raises(ValueError, match="aucune table"):
        parser.parse("dummy.md")
