import pytest
from unittest.mock import patch
from ecoia.core.llm_factory import LLMFactory
from ecoia.config import settings


def test_get_llm_openai():
    with patch("langchain_openai.ChatOpenAI") as mock_openai:
        LLMFactory.get_llm(provider="openai", model_name="gpt-4", temperature=0.5)
        mock_openai.assert_called_once_with(model="gpt-4", temperature=0.5, openai_api_key=settings.OPENAI_API_KEY)


def test_get_llm_bedrock():
    with patch("langchain_aws.ChatBedrock") as mock_bedrock:
        LLMFactory.get_llm(provider="bedrock", model_name="anthropic.claude-3-sonnet", temperature=0.7)
        mock_bedrock.assert_called_once_with(
            model_id="anthropic.claude-3-sonnet",
            region_name=settings.AWS_REGION,
            credentials_profile_name=None,
            model_kwargs={"temperature": 0.7},
        )


def test_get_llm_mistral():
    with patch("langchain_mistralai.ChatMistralAI") as mock_mistral:
        LLMFactory.get_llm(provider="mistral", model_name="mistral-large-latest", temperature=0.2)
        mock_mistral.assert_called_once_with(
            model="mistral-large-latest",
            temperature=0.2,
            mistral_api_key=settings.MISTRAL_API_KEY,
        )


def test_get_llm_unsupported():
    with pytest.raises(ValueError, match="Unsupported LLM provider: unknown"):
        LLMFactory.get_llm(provider="unknown")


def test_get_llm_default():
    with patch("langchain_mistralai.ChatMistralAI") as mock_mistral:
        LLMFactory.get_llm()
        mock_mistral.assert_called_once()
