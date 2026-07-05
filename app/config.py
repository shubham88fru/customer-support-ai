from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./customer_support_ai.db"

    mailbox_provider: str = "fake"
    mailslurp_api_key: str = ""
    mailslurp_inbox_id: str = ""
    gmail_credentials_file: str = "credentials.json"
    gmail_token_file: str = "token.json"
    gmail_query: str = "in:inbox is:unread -from:me"
    gmail_max_results: int = Field(default=20, ge=1, le=100)
    gmail_auth_browser: str = ""

    llm_provider: str = "fake"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    auto_send_enabled: bool = True
    auto_send_min_routing_confidence: float = Field(default=0.75, ge=0, le=1)
    auto_send_min_reply_confidence: float = Field(default=0.75, ge=0, le=1)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
