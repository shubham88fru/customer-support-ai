from functools import lru_cache

from app.agents.factory import build_llm_client
from app.agents.llm import LLMClient
from app.config import Settings, get_settings
from app.mailbox.base import MailboxProvider
from app.mailbox.factory import build_mailbox_provider


@lru_cache
def get_mailbox_provider() -> MailboxProvider:
    return build_mailbox_provider(get_settings())


@lru_cache
def get_llm_client() -> LLMClient:
    return build_llm_client(get_settings())


def get_app_settings() -> Settings:
    return get_settings()

