from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.llm import LLMClient
from app.agents.support import draft_reply, route_email
from app.config import Settings
from app.mailbox.base import MailboxProvider
from app.models import AgentRun, EmailMessage, Reply, Ticket, utcnow
from app.schemas import MailboxMessage, ReplyDraft, RoutingDecision
from app.services.ticketing import create_ticket_for_email, get_email_by_provider_id, mark_email_processed, store_inbound_email


@dataclass
class PollResult:
    seen: int = 0
    created: int = 0
    skipped: int = 0
    sent: int = 0
    needs_review: int = 0
    failed: int = 0


class IngestionService:
    def __init__(self, db: Session, mailbox: MailboxProvider, llm: LLMClient, settings: Settings) -> None:
        self.db = db
        self.mailbox = mailbox
        self.llm = llm
        self.settings = settings

    def poll(self) -> PollResult:
        result = PollResult()
        for message_id in self.mailbox.list_new_messages():
            result.seen += 1
            if get_email_by_provider_id(self.db, self.mailbox.name, message_id):
                self.mailbox.mark_processed(message_id)
                result.skipped += 1
                continue
            try:
                message = self.mailbox.get_message(message_id)
                outcome = self.process_message(message)
                result.created += 1
                if outcome == "sent":
                    result.sent += 1
                elif outcome == "needs_review":
                    result.needs_review += 1
                else:
                    result.failed += 1
                self.mailbox.mark_processed(message_id)
                self.db.commit()
            except Exception:
                self.db.rollback()
                result.failed += 1
        return result

    def process_message(self, message: MailboxMessage) -> str:
        email = store_inbound_email(self.db, message)
        ticket = create_ticket_for_email(self.db, email)

        decision = self._route(ticket, message)
        reply = self._draft(ticket, message, decision)
        db_reply = Reply(ticket_id=ticket.id, email_message_id=email.id, body=reply.normalized_body, confidence=reply.confidence)
        self.db.add(db_reply)
        self.db.flush()

        ticket.domain = decision.domain
        ticket.priority = decision.priority
        ticket.routing_confidence = decision.confidence
        ticket.reply_confidence = reply.confidence
        ticket.assigned_agent = decision.domain

        should_send = (
            decision.confidence >= self.settings.auto_send_min_routing_confidence
            and reply.confidence >= self.settings.auto_send_min_reply_confidence
            and not reply.needs_review
            and bool(reply.normalized_body)
        )
        if not should_send:
            ticket.status = "needs_review"
            db_reply.status = "needs_review"
            mark_email_processed(email)
            return "needs_review"

        try:
            sent = self.mailbox.send_reply(message, reply.normalized_body)
            outbound = EmailMessage(
                provider=self.mailbox.name,
                provider_message_id=sent.provider_message_id or f"sent-ticket-{ticket.id}",
                direction="outbound",
                from_address=(message.to_addresses[0] if message.to_addresses else "support@example.test"),
                to_addresses=[message.from_address],
                subject=_reply_subject(message.subject),
                text_body=reply.normalized_body,
                html_body="",
                received_at=utcnow(),
                processed_at=utcnow(),
            )
            self.db.add(outbound)
            self.db.flush()
            db_reply.status = "sent"
            db_reply.provider_message_id = sent.provider_message_id
            db_reply.sent_at = utcnow()
            ticket.status = "replied"
            mark_email_processed(email)
            return "sent"
        except Exception as exc:
            db_reply.status = "send_failed"
            db_reply.error = str(exc)
            ticket.status = "send_failed"
            mark_email_processed(email)
            return "failed"

    def retry_route(self, ticket_id: int) -> Ticket:
        ticket = self.db.get(Ticket, ticket_id)
        if not ticket or not ticket.latest_email:
            raise ValueError(f"Ticket {ticket_id} was not found or has no email")
        message = _message_from_email(ticket.latest_email)
        decision = self._route(ticket, message)
        ticket.domain = decision.domain
        ticket.priority = decision.priority
        ticket.routing_confidence = decision.confidence
        ticket.assigned_agent = decision.domain
        self.db.commit()
        return ticket

    def retry_reply(self, ticket_id: int) -> Reply:
        ticket = self.db.get(Ticket, ticket_id)
        if not ticket or not ticket.latest_email:
            raise ValueError(f"Ticket {ticket_id} was not found or has no email")
        message = _message_from_email(ticket.latest_email)
        decision = RoutingDecision(domain=ticket.domain, priority=ticket.priority, confidence=ticket.routing_confidence)
        reply = self._draft(ticket, message, decision)
        db_reply = Reply(ticket_id=ticket.id, email_message_id=ticket.latest_email.id, body=reply.normalized_body, confidence=reply.confidence)
        self.db.add(db_reply)
        self.db.flush()
        if reply.needs_review or reply.confidence < self.settings.auto_send_min_reply_confidence:
            db_reply.status = "needs_review"
            ticket.status = "needs_review"
        else:
            sent = self.mailbox.send_reply(message, reply.normalized_body)
            db_reply.status = "sent"
            db_reply.provider_message_id = sent.provider_message_id
            db_reply.sent_at = utcnow()
            ticket.status = "replied"
        self.db.commit()
        return db_reply

    def _route(self, ticket: Ticket, message: MailboxMessage) -> RoutingDecision:
        try:
            decision = route_email(self.llm, message)
            self.db.add(
                AgentRun(
                    ticket_id=ticket.id,
                    agent_name="router",
                    run_type="routing",
                    input={"subject": message.subject, "body": message.text_body or message.html_body},
                    output=decision.model_dump(),
                    status="succeeded",
                )
            )
            return decision
        except Exception as exc:
            self.db.add(
                AgentRun(
                    ticket_id=ticket.id,
                    agent_name="router",
                    run_type="routing",
                    input={"subject": message.subject},
                    output={},
                    status="failed",
                    error=str(exc),
                )
            )
            raise

    def _draft(self, ticket: Ticket, message: MailboxMessage, decision: RoutingDecision) -> ReplyDraft:
        try:
            reply = draft_reply(self.llm, message, decision)
            self.db.add(
                AgentRun(
                    ticket_id=ticket.id,
                    agent_name=decision.domain,
                    run_type="reply",
                    input={"subject": message.subject, "body": message.text_body or message.html_body},
                    output=reply.model_dump(),
                    status="succeeded",
                )
            )
            return reply
        except Exception as exc:
            self.db.add(
                AgentRun(
                    ticket_id=ticket.id,
                    agent_name=decision.domain,
                    run_type="reply",
                    input={"subject": message.subject},
                    output={},
                    status="failed",
                    error=str(exc),
                )
            )
            raise


def list_tickets(db: Session) -> list[Ticket]:
    return list(db.scalars(select(Ticket).order_by(Ticket.created_at.desc())))


def get_ticket(db: Session, ticket_id: int) -> Ticket | None:
    return db.get(Ticket, ticket_id)


def _message_from_email(email: EmailMessage) -> MailboxMessage:
    return MailboxMessage(
        provider=email.provider,
        provider_message_id=email.provider_message_id,
        from_address=email.from_address,
        to_addresses=email.to_addresses,
        subject=email.subject,
        text_body=email.text_body,
        html_body=email.html_body,
        received_at=email.received_at,
    )


def _reply_subject(subject: str) -> str:
    if subject.lower().startswith("re:"):
        return subject
    return f"Re: {subject}" if subject else "Re: Your support request"

