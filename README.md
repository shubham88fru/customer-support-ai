# Customer Support AI

A learning project for a multi-agent customer support system.

The app ingests customer emails, creates tickets, routes each ticket to a specialist support agent, generates a reply, and sends the reply when confidence thresholds are met.

## Stack

- Python FastAPI
- SQLAlchemy
- Postgres in production-style setups, SQLite by default for local development
- MailSlurp mailbox adapter
- OpenAI-compatible LLM adapter
- Server-rendered admin dashboard

## Quickstart

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
uvicorn app.main:app --reload
```

Open:

- Admin dashboard: http://127.0.0.1:8000
- API docs: http://127.0.0.1:8000/docs

The default `.env.example` uses fake mailbox and fake LLM providers so the app can run without API keys.

## Using MailSlurp and OpenAI

Set these values in `.env`:

```bash
MAILBOX_PROVIDER=mailslurp
MAILSLURP_API_KEY=...
MAILSLURP_INBOX_ID=...

LLM_PROVIDER=openai
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4o-mini
```

Then run:

```bash
uvicorn app.main:app --reload
```

Trigger polling manually:

```bash
curl -X POST http://127.0.0.1:8000/ingest/poll
```

## Current Scope

This is a v1 implementation:

- Polling-based email ingestion
- MailSlurp provider adapter
- Fake provider for local demos/tests
- LLM router and specialist agents
- Auto-send with confidence fallback to `needs_review`
- Minimal admin UI

