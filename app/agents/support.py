from app.agents.llm import LLMClient
from app.schemas import MailboxMessage, ReplyDraft, RoutingDecision


ROUTER_SYSTEM_PROMPT = """
You route customer support emails to exactly one domain.
Return only JSON with keys: domain, priority, confidence, reasoning.
Allowed domains: payments_cancellations, bugs, service_issues, general_support.
Allowed priorities: low, normal, high, urgent.
Confidence must be between 0 and 1.
""".strip()


SPECIALIST_PROMPTS = {
    "payments_cancellations": "You are a payments and cancellations support agent. Be clear about billing, cancellation, and refund next steps.",
    "bugs": "You are a bug support agent. Acknowledge the issue, ask for only essential missing details, and avoid promising an unverified fix.",
    "service_issues": "You are a service issues support agent. Acknowledge impact, give clear status language, and avoid inventing outage facts.",
    "general_support": "You are a general customer support agent. Provide concise, helpful support and escalate uncertainty.",
}


def route_email(llm: LLMClient, message: MailboxMessage) -> RoutingDecision:
    payload = llm.complete_json(
        ROUTER_SYSTEM_PROMPT,
        _email_prompt(message),
    )
    return RoutingDecision.model_validate(payload)


def draft_reply(llm: LLMClient, message: MailboxMessage, decision: RoutingDecision) -> ReplyDraft:
    system_prompt = f"""
{SPECIALIST_PROMPTS[decision.domain]}
Return only JSON with keys: body, confidence, needs_review, reasoning.
The body must be a customer-facing plain text email reply.
Do not invent account-specific facts. If the request requires account access, say the team will review it.
Confidence must be between 0 and 1.
""".strip()
    payload = llm.complete_json(system_prompt, _email_prompt(message))
    return ReplyDraft.model_validate(payload)


def _email_prompt(message: MailboxMessage) -> str:
    return f"""
From: {message.from_address}
To: {", ".join(message.to_addresses)}
Subject: {message.subject}

{message.text_body or message.html_body}
""".strip()

