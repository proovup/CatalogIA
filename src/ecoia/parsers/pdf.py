from typing import Any, Dict
import PyPDF2
from ecoia.parsers.base import BaseParser


class PDFParser(BaseParser):
    def parse(self, file_path: str) -> Dict[str, Any]:
        self.validate_extension(file_path, [".pdf"])

        text_content = ""
        num_pages = 0

        with open(file_path, "rb") as file:
            reader = PyPDF2.PdfReader(file)
            num_pages = len(reader.pages)

            for page in reader.pages:
                text_content += page.extract_text() + "\n"

        return {
            "type": "pdf",
            "content": text_content,
            "metadata": {"num_pages": num_pages},
        }
