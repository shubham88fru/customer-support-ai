from datetime import datetime, timezone
from itertools import count

from app.mailbox.base import MailboxProvider
from app.schemas import MailboxMessage, SentMessage


class FakeMailboxProvider(MailboxProvider):
    name = "fake"

    def __init__(self) -> None:
        self._messages = {
            "fake-1": MailboxMessage(
                provider=self.name,
                provider_message_id="fake-1",
                from_address="customer@example.com",
                to_addresses=["support@example.test"],
                subject="Cancel my subscription",
                text_body="Hi, please cancel my subscription and confirm that I will not be billed again.",
                received_at=datetime.now(timezone.utc),
            )
        }
        self._processed: set[str] = set()
        self._sent_ids = count(1)

    def list_new_messages(self) -> list[str]:
        return [message_id for message_id in self._messages if message_id not in self._processed]

    def get_message(self, provider_message_id: str) -> MailboxMessage:
        return self._messages[provider_message_id]

    def send_reply(self, original: MailboxMessage, body: str) -> SentMessage:
        return SentMessage(provider_message_id=f"fake-sent-{next(self._sent_ids)}")

    def mark_processed(self, provider_message_id: str) -> None:
        self._processed.add(provider_message_id)

