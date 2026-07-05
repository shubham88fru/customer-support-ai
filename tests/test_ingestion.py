from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.agents.llm import FakeLLMClient
from app.config import Settings
from app.db import Base
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
    assert reply is not None
    assert reply.status == "sent"
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

