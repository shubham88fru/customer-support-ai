from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import EmailMessage, Ticket, utcnow
from app.schemas import MailboxMessage


def get_email_by_provider_id(db: Session, provider: str, provider_message_id: str) -> EmailMessage | None:
    return db.scalar(
        select(EmailMessage).where(
            EmailMessage.provider == provider,
            EmailMessage.provider_message_id == provider_message_id,
        )
    )


def store_inbound_email(db: Session, message: MailboxMessage) -> EmailMessage:
    existing = get_email_by_provider_id(db, message.provider, message.provider_message_id)
    if existing:
        return existing

    email = EmailMessage(
        provider=message.provider,
        provider_message_id=message.provider_message_id,
        direction="inbound",
        from_address=message.from_address,
        to_addresses=message.to_addresses,
        subject=message.subject,
        text_body=message.text_body,
        html_body=message.html_body,
        received_at=message.received_at,
    )
    db.add(email)
    db.flush()
    return email


def create_ticket_for_email(db: Session, email: EmailMessage) -> Ticket:
    ticket = Ticket(
        customer_email=email.from_address,
        subject=email.subject,
        status="new",
        latest_email_id=email.id,
    )
    db.add(ticket)
    db.flush()
    return ticket


def mark_email_processed(email: EmailMessage) -> None:
    email.processed_at = utcnow()

