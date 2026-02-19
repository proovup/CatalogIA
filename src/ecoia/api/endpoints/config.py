from fastapi import APIRouter
from pydantic import BaseModel
from typing import Dict
from ecoia.config import settings

router = APIRouter(prefix="/config", tags=["config"])


class ConfigStatus(BaseModel):
    providers: Dict[str, bool]
    defaults: Dict[str, str]
    env_vars: Dict[str, bool]


@router.get("/", response_model=ConfigStatus)
async def get_config_status():
    """
    Returns the status of the configuration, including:
    - Which providers are configured (API keys present)
    - Default settings from the backend
    - Status of critical environment variables
    """

    # Check providers
    providers = {
        "openai": bool(settings.OPENAI_API_KEY),
        "anthropic": bool(settings.ANTHROPIC_API_KEY),
        "mistral": bool(settings.MISTRAL_API_KEY),
        "bedrock": bool(settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY),
    }

    # Check env vars (generic check for key variables)
    env_vars = {
        "DATABASE_URL": bool(settings.DATABASE_URL),
        "REDIS_URL": bool(settings.REDIS_URL),
        "OPENAI_API_KEY": bool(settings.OPENAI_API_KEY),
        "ANTHROPIC_API_KEY": bool(settings.ANTHROPIC_API_KEY),
        "MISTRAL_API_KEY": bool(settings.MISTRAL_API_KEY),
        "AWS_CREDENTIALS": bool(settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY),
    }

    return {
        "providers": providers,
        "defaults": {
            "provider": settings.LLM_PROVIDER,
            "model": settings.LLM_MODEL,
        },
        "env_vars": env_vars,
    }
