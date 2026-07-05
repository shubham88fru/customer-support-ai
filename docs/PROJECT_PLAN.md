# Customer Support AI Project Plan

## Purpose

Build a learning project for a multi-agent customer support system.

Customers send emails to the system. The system reads those emails, creates tickets, routes each ticket to the right support agent, and sends a response back to the customer.

The project is intended to teach practical multi-agent system design using a realistic customer support workflow.

## Decisions So Far

- Stack: Python FastAPI.
- Persistence: Postgres preferred.
- Mailbox provider: MailSlurp.
- Mailbox architecture: use a provider adapter, with MailSlurp as the first concrete implementation.
- Email ingestion: start with polling; add webhooks later if needed.
- Agent style: LLM agents.
- Interface: API plus a minimal admin dashboard.
- Reply flow: auto-send replies when confidence is high.
- Safety fallback: low-confidence or failed cases should be marked `needs_review`.
- `AIThreadsAccount` is not being considered because it does not appear to be a legitimate or documented public mailbox service.

## System Flow

1. A customer sends an email to a MailSlurp inbox.
2. The backend polls MailSlurp for new messages.
3. The system deduplicates inbound messages by provider message id.
4. The raw email is stored.
5. The system creates or updates a support ticket.
6. A router agent classifies the ticket domain.
7. A specialist support agent handles the ticket.
8. The specialist agent generates a reply.
9. If confidence thresholds are met, the system sends the reply through MailSlurp.
10. If confidence is low or sending fails, the ticket is marked `needs_review`.

## Agent Domains

The first version should include these specialist domains:

- Payments and cancellations.
- Bugs.
- Service issues.
- General support.

## Architecture

Use a `MailboxProvider` interface so the application does not depend directly on MailSlurp outside the mailbox integration layer.

Initial provider methods:

- `list_new_messages`
- `get_message`
- `send_reply`
- `mark_processed`

Concrete v1 implementation:

- `MailSlurpMailboxProvider`

Core database tables:

- `email_messages`: raw inbound and outbound email metadata and body.
- `tickets`: customer issue, status, domain, priority, confidence, assigned agent.
- `agent_runs`: router and specialist decisions, prompts, outputs, errors, token/cost metadata.
- `replies`: generated response, send status, provider message id.

## Initial API Surface

- `GET /health`
- `POST /ingest/poll`
- `GET /tickets`
- `GET /tickets/{ticket_id}`
- `POST /tickets/{ticket_id}/reply/retry`
- `POST /tickets/{ticket_id}/route/retry`

## Environment Variables

- `MAILSLURP_API_KEY`
- `MAILSLURP_INBOX_ID`
- `OPENAI_API_KEY`
- `DATABASE_URL`
- `AUTO_SEND_MIN_ROUTING_CONFIDENCE`
- `AUTO_SEND_MIN_REPLY_CONFIDENCE`

## Admin Dashboard

The first admin UI should be minimal but useful:

- Ticket list with status, domain, priority, and timestamps.
- Ticket detail page with the original email.
- Routing decision and confidence.
- Specialist agent output.
- Outbound reply status.
- Agent trace or run history.
- Retry controls for routing or reply sending failures.

## Testing Plan

- Unit tests for email parsing, deduplication, ticket creation, routing schema validation, and mailbox provider behavior.
- Agent tests with mocked LLM responses for each domain.
- Integration test using a fake mailbox provider for ingest to ticket to route to reply to send.
- Manual MailSlurp acceptance test:
  - Send payment, cancellation, bug, and service issue emails to the dev inbox.
  - Confirm tickets are created.
  - Confirm each ticket is assigned to the correct specialist domain.
  - Confirm replies are sent when confidence is high.
  - Confirm low-confidence cases are marked `needs_review`.
  - Confirm the dashboard shows raw email, routing decision, agent trace, and outbound reply state.

## Current Repo State

At the time this plan was saved:

- Workspace path: `/Users/shubham/Desktop/Projects/customer-support-ai`
- The folder was empty except for this planning document.
- The folder was not initialized as a Git repository.

## Resume Instructions

If the original chat session is lost, open the same workspace and paste this prompt into a new Codex session:

```text
Continue my customer-support-ai project from the saved plan in docs/PROJECT_PLAN.md.

First, read that file and inspect the repository. Then help me implement the first version:
- Python FastAPI backend
- Postgres persistence
- MailSlurp mailbox provider
- LLM router and specialist agents
- API plus minimal admin dashboard
- auto-send replies when confidence is high, otherwise mark tickets needs_review
```

If you want to continue planning before implementation, use this prompt instead:

```text
Continue planning my customer-support-ai project from docs/PROJECT_PLAN.md.

Read the saved plan, inspect the repository, and refine the architecture before implementation.
```
