import pytest
import os
from ecoia.parsers.text import TextParser


def test_text_parser():
    parser = TextParser()

    # Create a dummy text file
    file_path = "test_parser.txt"
    content = "Hello world\nThis is a test."
    with open(file_path, "w") as f:
        f.write(content)

    try:
        result = parser.parse(file_path)
        assert result["type"] == "text"
        assert result["content"] == content
        assert result["metadata"]["format"] == "text"
        assert result["metadata"]["length"] == len(content)
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)


def test_csv_parser():
    parser = TextParser()

    # Create a dummy csv file
    file_path = "test_parser.csv"
    content = "col1,col2\nval1,val2"
    with open(file_path, "w") as f:
        f.write(content)

    try:
        result = parser.parse(file_path)
        assert result["type"] == "text"
        assert result["metadata"]["format"] == "csv"
        assert len(result["content"]) == 2
        assert result["content"][0] == ["col1", "col2"]
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)


def test_invalid_extension():
    parser = TextParser()
    with pytest.raises(ValueError):
        parser.validate_extension("test.pdf", [".txt"])
