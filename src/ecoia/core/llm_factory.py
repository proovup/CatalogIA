from typing import Optional, Any
from langchain_core.language_models.chat_models import BaseChatModel
from ecoia.config import settings


class LLMFactory:
    """Factory to create LangChain chat model instances dynamically."""

    @staticmethod
    def get_llm(
        provider: Optional[str] = None,
        model_name: Optional[str] = None,
        temperature: float = 0,
        **kwargs: Any,
    ) -> BaseChatModel:
        provider = provider or settings.LLM_PROVIDER
        model_name = model_name or settings.LLM_MODEL

        if provider == "openai":
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(
                model=model_name,
                temperature=temperature,
                openai_api_key=settings.OPENAI_API_KEY,
                **kwargs,
            )

        elif provider == "bedrock":
            from langchain_aws import ChatBedrock

            return ChatBedrock(
                model_id=model_name,
                region_name=settings.AWS_REGION,
                credentials_profile_name=kwargs.pop("credentials_profile_name", None),
                model_kwargs={"temperature": temperature, **kwargs},
            )

        elif provider == "anthropic":
            from langchain_anthropic import ChatAnthropic

            return ChatAnthropic(
                model=model_name or "claude-3-5-sonnet-latest",
                temperature=temperature,
                anthropic_api_key=settings.ANTHROPIC_API_KEY,
                **kwargs,
            )

        elif provider == "mistral":
            from langchain_mistralai import ChatMistralAI

            return ChatMistralAI(
                model=model_name,
                temperature=temperature,
                mistral_api_key=settings.MISTRAL_API_KEY,
                **kwargs,
            )

        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")
