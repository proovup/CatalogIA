from abc import ABC, abstractmethod
from typing import Any, Dict, List
import os


class BaseParser(ABC):
    @abstractmethod
    def parse(self, file_path: str) -> Dict[str, Any]:
        """
        Parse the file and return raw data.
        """
        pass

    def validate_extension(self, file_path: str, allowed_extensions: List[str]):
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in allowed_extensions:
            raise ValueError(
                f"Invalid file extension {ext}. Expected one of {allowed_extensions}"
            )
