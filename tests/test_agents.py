from app.agents.llm import FakeLLMClient
from app.agents.support import draft_reply, route_email
from app.schemas import MailboxMessage


def test_fake_router_detects_payments_and_cancellations() -> None:
    message = MailboxMessage(
        provider="fake",
        provider_message_id="1",
        from_address="customer@example.com",
        subject="Please cancel",
        text_body="Cancel my subscription and refund the latest invoice.",
    )

    decision = route_email(FakeLLMClient(), message)

    assert decision.domain == "payments_cancellations"
    assert decision.confidence >= 0.75


def test_fake_specialist_generates_reply() -> None:
    llm = FakeLLMClient()
    message = MailboxMessage(
        provider="fake",
        provider_message_id="1",
        from_address="customer@example.com",
        subject="Service is slow",
        text_body="The service is very slow today.",
    )
    decision = route_email(llm, message)

    reply = draft_reply(llm, message, decision)

    assert reply.body
    assert reply.confidence >= 0.75

