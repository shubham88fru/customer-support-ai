import logging

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.agents.llm import LLMClient
from app.config import Settings
from app.db import get_db, init_db
from app.dependencies import get_app_settings, get_llm_client, get_mailbox_provider
from app.mailbox.base import MailboxProvider
from app.services.ingestion import IngestionService, get_ticket, list_tickets

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

app = FastAPI(title="Customer Support AI")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/ingest/poll")
def poll_mailbox(
    db: Session = Depends(get_db),
    mailbox: MailboxProvider = Depends(get_mailbox_provider),
    llm: LLMClient = Depends(get_llm_client),
    settings: Settings = Depends(get_app_settings),
) -> dict[str, int]:
    service = IngestionService(db=db, mailbox=mailbox, llm=llm, settings=settings)
    return service.poll().__dict__


@app.get("/tickets")
def tickets_index(db: Session = Depends(get_db)) -> list[dict[str, object]]:
    return [_ticket_summary(ticket) for ticket in list_tickets(db)]


@app.get("/tickets/{ticket_id}")
def ticket_detail_api(ticket_id: int, db: Session = Depends(get_db)) -> dict[str, object]:
    ticket = get_ticket(db, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return _ticket_detail(ticket)


@app.post("/tickets/{ticket_id}/reply/retry")
def retry_reply(
    ticket_id: int,
    db: Session = Depends(get_db),
    mailbox: MailboxProvider = Depends(get_mailbox_provider),
    llm: LLMClient = Depends(get_llm_client),
    settings: Settings = Depends(get_app_settings),
) -> dict[str, object]:
    service = IngestionService(db=db, mailbox=mailbox, llm=llm, settings=settings)
    try:
        reply = service.retry_reply(ticket_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"reply_id": reply.id, "status": reply.status}


@app.post("/tickets/{ticket_id}/route/retry")
def retry_route(
    ticket_id: int,
    db: Session = Depends(get_db),
    mailbox: MailboxProvider = Depends(get_mailbox_provider),
    llm: LLMClient = Depends(get_llm_client),
    settings: Settings = Depends(get_app_settings),
) -> dict[str, object]:
    service = IngestionService(db=db, mailbox=mailbox, llm=llm, settings=settings)
    try:
        ticket = service.retry_route(ticket_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _ticket_summary(ticket)


@app.get("/", response_class=HTMLResponse)
def admin_home(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    return templates.TemplateResponse(request, "tickets.html", {"tickets": list_tickets(db)})


@app.get("/admin/tickets/{ticket_id}", response_class=HTMLResponse)
def admin_ticket_detail(request: Request, ticket_id: int, db: Session = Depends(get_db)) -> HTMLResponse:
    ticket = get_ticket(db, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return templates.TemplateResponse(request, "ticket_detail.html", {"ticket": ticket})


@app.post("/admin/ingest/poll")
def admin_poll_mailbox(
    db: Session = Depends(get_db),
    mailbox: MailboxProvider = Depends(get_mailbox_provider),
    llm: LLMClient = Depends(get_llm_client),
    settings: Settings = Depends(get_app_settings),
) -> RedirectResponse:
    service = IngestionService(db=db, mailbox=mailbox, llm=llm, settings=settings)
    service.poll()
    return RedirectResponse("/", status_code=303)


@app.post("/admin/tickets/{ticket_id}/reply/retry")
def admin_retry_reply(
    ticket_id: int,
    db: Session = Depends(get_db),
    mailbox: MailboxProvider = Depends(get_mailbox_provider),
    llm: LLMClient = Depends(get_llm_client),
    settings: Settings = Depends(get_app_settings),
) -> RedirectResponse:
    service = IngestionService(db=db, mailbox=mailbox, llm=llm, settings=settings)
    service.retry_reply(ticket_id)
    return RedirectResponse(f"/admin/tickets/{ticket_id}", status_code=303)


@app.post("/admin/tickets/{ticket_id}/route/retry")
def admin_retry_route(
    ticket_id: int,
    db: Session = Depends(get_db),
    mailbox: MailboxProvider = Depends(get_mailbox_provider),
    llm: LLMClient = Depends(get_llm_client),
    settings: Settings = Depends(get_app_settings),
) -> RedirectResponse:
    service = IngestionService(db=db, mailbox=mailbox, llm=llm, settings=settings)
    service.retry_route(ticket_id)
    return RedirectResponse(f"/admin/tickets/{ticket_id}", status_code=303)


def _ticket_summary(ticket) -> dict[str, object]:
    return {
        "id": ticket.id,
        "customer_email": ticket.customer_email,
        "subject": ticket.subject,
        "status": ticket.status,
        "domain": ticket.domain,
        "priority": ticket.priority,
        "routing_confidence": ticket.routing_confidence,
        "reply_confidence": ticket.reply_confidence,
        "created_at": ticket.created_at,
        "updated_at": ticket.updated_at,
    }


def _ticket_detail(ticket) -> dict[str, object]:
    payload = _ticket_summary(ticket)
    payload.update(
        {
            "latest_email": {
                "from_address": ticket.latest_email.from_address if ticket.latest_email else "",
                "to_addresses": ticket.latest_email.to_addresses if ticket.latest_email else [],
                "subject": ticket.latest_email.subject if ticket.latest_email else "",
                "text_body": ticket.latest_email.text_body if ticket.latest_email else "",
            },
            "agent_runs": [
                {
                    "id": run.id,
                    "agent_name": run.agent_name,
                    "run_type": run.run_type,
                    "status": run.status,
                    "output": run.output,
                    "error": run.error,
                    "created_at": run.created_at,
                }
                for run in ticket.agent_runs
            ],
            "replies": [
                {
                    "id": reply.id,
                    "status": reply.status,
                    "confidence": reply.confidence,
                    "body": reply.body,
                    "error": reply.error,
                    "provider_message_id": reply.provider_message_id,
                    "sent_at": reply.sent_at,
                }
                for reply in ticket.replies
            ],
        }
    )
    return payload
