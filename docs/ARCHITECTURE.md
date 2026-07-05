# Architecture

This project is a polling-based multi-agent customer support system. It reads customer email, creates a ticket, routes the issue to the right specialist agent, drafts a reply, and sends the response when confidence checks pass.

## System Diagram

```mermaid
flowchart LR
    customer["Customer"] --> mailbox_account["Mailbox Account<br/>Gmail / MailSlurp"]

    admin["Admin Dashboard<br/>Server-rendered UI"] --> fastapi["FastAPI App"]
    api["API Client<br/>curl / tests / tools"] --> fastapi

    fastapi --> ingestion["IngestionService"]
    ingestion --> mailbox_provider["MailboxProvider Interface"]
    mailbox_provider --> gmail["Gmail Provider"]
    mailbox_provider --> mailslurp["MailSlurp Provider"]
    mailbox_provider --> fake_mailbox["Fake Mailbox<br/>local tests"]

    gmail --> mailbox_account
    mailslurp --> mailbox_account
    fake_mailbox --> ingestion

    ingestion --> dedupe["Deduplicate<br/>provider message id"]
    dedupe --> ticketing["Ticketing Service"]
    ticketing --> db["Database<br/>email_messages<br/>tickets<br/>agent_runs<br/>replies"]

    ingestion --> router["Router Agent<br/>classifies domain, priority, confidence"]
    router --> llm_provider["LLM Provider<br/>OpenAI / fake"]

    router --> specialist{"Specialist Domain"}
    specialist --> payments["Payments + Cancellations Agent"]
    specialist --> bugs["Bugs Agent"]
    specialist --> service["Service Issues Agent"]
    specialist --> general["General Support Agent"]

    payments --> llm_provider
    bugs --> llm_provider
    service --> llm_provider
    general --> llm_provider

    payments --> reply_policy["Reply Policy<br/>confidence thresholds + review fallback"]
    bugs --> reply_policy
    service --> reply_policy
    general --> reply_policy

    reply_policy --> replies["Store Reply<br/>status, confidence, handled_by_agent"]
    replies --> db
    reply_policy --> send_decision{"Auto-send allowed?"}
    send_decision -->|yes| mailbox_provider
    send_decision -->|no| review["needs_review / drafted"]
    mailbox_provider --> outbound["Outbound Email Reply"]
    outbound --> customer
```

## Runtime Flow

1. A customer sends an email with a subject such as `[CUST_AGENT_SUPPORT] - can I get a refund please`.
2. An admin or test client triggers mailbox polling.
3. The mailbox provider fetches at most one matching unread email.
4. The ingestion service stores the raw email and creates a ticket.
5. The router agent chooses a domain, priority, and confidence score.
6. The selected specialist agent drafts a response.
7. The system stores the reply with the agent that handled it.
8. If confidence thresholds pass and auto-send is enabled, the provider sends the reply.
9. The dashboard shows ticket status, routing, assigned agent, reply status, and agent run traces.

## Main Components

- `app/mailbox/*`: provider adapters for Gmail, MailSlurp, and fake local mailboxes.
- `app/services/ingestion.py`: orchestration for polling, routing, drafting, sending, and retrying.
- `app/services/ticketing.py`: email persistence and ticket creation.
- `app/agents/*`: router and specialist support agents.
- `app/models.py`: database schema for emails, tickets, agent runs, and replies.
- `app/templates/*`: admin dashboard views.
