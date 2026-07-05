from abc import ABC, abstractmethod

from app.schemas import MailboxMessage, SentMessage


class MailboxProvider(ABC):
    name: str

    @abstractmethod
    def list_new_messages(self) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def get_message(self, provider_message_id: str) -> MailboxMessage:
        raise NotImplementedError

    @abstractmethod
    def send_reply(self, original: MailboxMessage, body: str) -> SentMessage:
        raise NotImplementedError

    @abstractmethod
    def mark_processed(self, provider_message_id: str) -> None:
        raise NotImplementedError

