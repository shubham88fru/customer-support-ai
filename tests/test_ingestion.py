from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.agents.llm import FakeLLMClient
from app.config import Settings
from app.db import Base
from app.mailbox.base import MailboxSendBlockedError
from app.mailbox.fake import FakeMailboxProvider
from app.models import EmailMessage, Reply, Ticket
from app.services.ingestion import IngestionService


def make_db() -> Session:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    return session_factory()


def test_poll_creates_ticket_and_sends_reply() -> None:
    db = make_db()
    settings = Settings(
        auto_send_enabled=True,
        auto_send_min_routing_confidence=0.75,
        auto_send_min_reply_confidence=0.75,
    )
    service = IngestionService(db=db, mailbox=FakeMailboxProvider(), llm=FakeLLMClient(), settings=settings)

    result = service.poll()

    assert result.seen == 1
    assert result.created == 1
    assert result.sent == 1

    ticket = db.scalar(select(Ticket))
    reply = db.scalar(select(Reply))
    emails = list(db.scalars(select(EmailMessage)))

    assert ticket is not None
    assert ticket.status == "replied"
    assert ticket.domain == "payments_cancellations"
    assert ticket.assigned_agent == "payments_cancellations"
    assert reply is not None
    assert reply.status == "sent"
    assert reply.handled_by_agent == "payments_cancellations"
    assert len(emails) == 2


def test_poll_deduplicates_processed_messages() -> None:
    db = make_db()
    mailbox = FakeMailboxProvider()
    settings = Settings()
    service = IngestionService(db=db, mailbox=mailbox, llm=FakeLLMClient(), settings=settings)

    first = service.poll()
    second = service.poll()

    assert first.created == 1
    assert second.created == 0
    assert second.seen == 0
    assert len(list(db.scalars(select(Ticket)))) == 1


def test_poll_marks_reply_as_drafted_when_auto_send_disabled() -> None:
    db = make_db()
    settings = Settings(auto_send_enabled=False)
    service = IngestionService(db=db, mailbox=FakeMailboxProvider(), llm=FakeLLMClient(), settings=settings)

    result = service.poll()

    ticket = db.scalar(select(Ticket))
    reply = db.scalar(select(Reply))

    assert result.drafted == 1
    assert result.sent == 0
    assert ticket is not None
    assert ticket.status == "drafted"
    assert reply is not None
    assert reply.status == "drafted"
    assert reply.handled_by_agent == "payments_cancellations"


def test_poll_marks_reply_as_send_blocked_for_provider_block() -> None:
    class BlockedMailbox(FakeMailboxProvider):
        def send_reply(self, original, body):
            raise MailboxSendBlockedError("External sending is disabled while your account has an active trial.")

    db = make_db()
    service = IngestionService(db=db, mailbox=BlockedMailbox(), llm=FakeLLMClient(), settings=Settings(auto_send_enabled=True))

    result = service.poll()

    ticket = db.scalar(select(Ticket))
    reply = db.scalar(select(Reply))

    assert result.send_blocked == 1
    assert result.failed == 0
    assert ticket is not None
    assert ticket.status == "send_blocked"
    assert reply is not None
    assert reply.status == "send_blocked"
    assert reply.handled_by_agent == "payments_cancellations"
    assert "External sending is disabled" in reply.error
