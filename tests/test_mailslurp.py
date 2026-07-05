import httpx

from app.mailbox.mailslurp import MailSlurpMailboxProvider
from app.schemas import MailboxMessage


def test_mailslurp_send_reply_uses_confirm_endpoint() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"id": "sent-123"})

    provider = MailSlurpMailboxProvider(api_key="test-key", inbox_id="inbox-123")
    provider.client = httpx.Client(transport=httpx.MockTransport(handler), base_url=provider.base_url)

    sent = provider.send_reply(
        MailboxMessage(
            provider="mailslurp",
            provider_message_id="email-123",
            from_address="customer@example.com",
            to_addresses=["support@example.test"],
            subject="Help",
            text_body="I need help.",
        ),
        "Thanks for writing in.",
    )

    assert sent.provider_message_id == "sent-123"
    assert requests[0].method == "POST"
    assert requests[0].url.path == "/inboxes/inbox-123/confirm"


def test_mailslurp_error_includes_response_body() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"message": "Sending disabled for this inbox"}, request=request)

    provider = MailSlurpMailboxProvider(api_key="test-key", inbox_id="inbox-123")
    provider.client = httpx.Client(transport=httpx.MockTransport(handler), base_url=provider.base_url)

    try:
        provider.send_reply(
            MailboxMessage(
                provider="mailslurp",
                provider_message_id="email-123",
                from_address="customer@example.com",
                subject="Help",
            ),
            "Thanks for writing in.",
        )
    except RuntimeError as exc:
        assert "status=403" in str(exc)
        assert "Sending disabled" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError")

