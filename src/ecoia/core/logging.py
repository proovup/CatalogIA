import logging
import sys
from ecoia.config import settings


def setup_logging():
    """Configure structured JSON logging for the application"""

    # Format defined to likely output JSON or structured text
    # For now, keeping it simple but structured
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    logging.basicConfig(
        level=logging.DEBUG if settings.DEBUG else logging.INFO,
        format=log_format,
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    # Set levels for third party libraries
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


# Initialize logging on import if needed, or call explicitely
setup_logging()
logger = logging.getLogger("ecoia")
