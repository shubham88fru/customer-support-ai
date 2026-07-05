from app.agents.llm import FakeLLMClient, LLMClient, OpenAILLMClient
from app.config import Settings


def build_llm_client(settings: Settings) -> LLMClient:
    provider = settings.llm_provider.lower()
    if provider == "fake":
        return FakeLLMClient()
    if provider == "openai":
        return OpenAILLMClient(api_key=settings.openai_api_key, model=settings.openai_model)
    raise ValueError(f"Unsupported LLM_PROVIDER: {settings.llm_provider}")

