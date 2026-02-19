from ecoia.parsers.excel import ExcelParser
from ecoia.parsers.pdf import PDFParser
from ecoia.parsers.word import WordParser
from ecoia.parsers.text import TextParser


class ParserFactory:
    @staticmethod
    def get_parser(file_path: str):
        import os

        ext = os.path.splitext(file_path)[1].lower()

        if ext in [".xlsx", ".xls"]:
            return ExcelParser()
        elif ext == ".pdf":
            return PDFParser()
        elif ext == ".docx":
            return WordParser()
        elif ext in [".txt", ".csv"]:
            return TextParser()
        else:
            raise ValueError(f"No parser available for extension {ext}")
