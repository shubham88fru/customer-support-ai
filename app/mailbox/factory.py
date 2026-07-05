from app.config import Settings
from app.mailbox.base import MailboxProvider
from app.mailbox.fake import FakeMailboxProvider
from app.mailbox.mailslurp import MailSlurpMailboxProvider


def build_mailbox_provider(settings: Settings) -> MailboxProvider:
    provider = settings.mailbox_provider.lower()
    if provider == "fake":
        return FakeMailboxProvider()
    if provider == "mailslurp":
        return MailSlurpMailboxProvider(
            api_key=settings.mailslurp_api_key,
            inbox_id=settings.mailslurp_inbox_id,
        )
    raise ValueError(f"Unsupported MAILBOX_PROVIDER: {settings.mailbox_provider}")

