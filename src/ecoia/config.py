import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    APP_NAME: str = "EcoIA Generator"
    VERSION: str = "0.1.0"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/ecoia"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Paths
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    UPLOAD_DIR: str = os.path.join(BASE_DIR, "uploads")

    # Classification
    CLASSIFICATION_CONFIDENCE_THRESHOLD: float = 0.6

    # LLM Settings
    LLM_PROVIDER: str = "mistral"  # openai, bedrock, mistral, anthropic
    LLM_MODEL: str = "mistral-large-latest"

    # OpenAI
    OPENAI_API_KEY: str = ""

    # AWS Bedrock
    AWS_REGION: str = "us-east-1"
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""

    # Mistral
    MISTRAL_API_KEY: str = ""

    # Anthropic
    ANTHROPIC_API_KEY: str = ""

    model_config = SettingsConfigDict(env_file=".env")


@lru_cache()
def get_settings():
    return Settings()


settings = get_settings()
