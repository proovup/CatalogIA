from typing import Any, Dict
import csv
import os
from ecoia.parsers.base import BaseParser


class TextParser(BaseParser):
    def parse(self, file_path: str) -> Dict[str, Any]:
        self.validate_extension(file_path, [".txt", ".csv"])

        ext = os.path.splitext(file_path)[1].lower()
        content = None
        metadata = {}

        if ext == ".csv":
            rows = []
            with open(file_path, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                for row in reader:
                    rows.append(row)
            content = rows
            metadata["format"] = "csv"
            metadata["rows"] = len(rows)
        else:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            metadata["format"] = "text"
            metadata["length"] = len(content)

        return {"type": "text", "content": content, "metadata": metadata}
