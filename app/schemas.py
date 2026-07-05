from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


SupportDomain = Literal["payments_cancellations", "bugs", "service_issues", "general_support"]
Priority = Literal["low", "normal", "high", "urgent"]


class MailboxMessage(BaseModel):
    provider: str
    provider_message_id: str
    from_address: str
    to_addresses: list[str] = Field(default_factory=list)
    subject: str = ""
    text_body: str = ""
    html_body: str = ""
    received_at: datetime | None = None


class SentMessage(BaseModel):
    provider_message_id: str


class RoutingDecision(BaseModel):
    domain: SupportDomain
    priority: Priority = "normal"
    confidence: float = Field(ge=0, le=1)
    reasoning: str = ""


class ReplyDraft(BaseModel):
    body: str
    confidence: float = Field(ge=0, le=1)
    needs_review: bool = False
    reasoning: str = ""

    @property
    def normalized_body(self) -> str:
        return self.body.strip()

