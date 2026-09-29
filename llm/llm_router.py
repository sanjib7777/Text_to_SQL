# services/llm/llm_factory.py

from llm.ollama_client import OllamaClient
from llm.cloud_client import CloudLLM
from settings import LLM_PLATFORM


class LLMFactory:

    @staticmethod
    def get_llm(
        model_name: str,
        llm_provider: str,
        platform: str | None = None
    ):
        platform = platform or LLM_PLATFORM

        if llm_provider == "ollama":
            return OllamaClient(model_name)
        else:
            return CloudLLM(model_name, platform=platform)