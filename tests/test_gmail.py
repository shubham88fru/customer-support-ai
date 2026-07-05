import base64
from email import message_from_bytes
from email.policy import default

from app.mailbox.gmail import GmailMailboxProvider


class _Request:
    def __init__(self, response):
        self.response = response

    def execute(self):
        return self.response


class _Messages:
    def __init__(self):
        self.list_args = None
        self.get_args = None
        self.send_args = None
        self.modify_args = None

    def list(self, **kwargs):
        self.list_args = kwargs
        return _Request({"messages": [{"id": "msg-1"}, {"id": "msg-2"}]})

    def get(self, **kwargs):
        self.get_args = kwargs
        body = base64.urlsafe_b64encode(b"Please cancel my subscription.").decode().rstrip("=")
        html = base64.urlsafe_b64encode(b"<p>Please cancel my subscription.</p>").decode().rstrip("=")
        return _Request(
            {
                "id": "msg-1",
                "internalDate": "1710000000000",
                "payload": {
                    "headers": [
                        {"name": "From", "value": "Shubham <customer@example.com>"},
                        {"name": "To", "value": "support@example.com"},
                        {"name": "Subject", "value": "Cancel subscription"},
                    ],
                    "parts": [
                        {"mimeType": "text/plain", "body": {"data": body}},
                        {"mimeType": "text/html", "body": {"data": html}},
                    ],
                },
            }
        )

    def send(self, **kwargs):
        self.send_args = kwargs
        return _Request({"id": "sent-1"})

    def modify(self, **kwargs):
        self.modify_args = kwargs
        return _Request({})


class _Users:
    def __init__(self, messages):
        self._messages = messages

    def messages(self):
        return self._messages


class _GmailService:
    def __init__(self):
        self.messages_resource = _Messages()

    def users(self):
        return _Users(self.messages_resource)


def test_gmail_lists_messages_with_query_and_limit() -> None:
    service = _GmailService()
    provider = GmailMailboxProvider(
        credentials_file="credentials.json",
        token_file="token.json",
        query="in:inbox is:unread",
        max_results=10,
        service=service,
    )

    ids = provider.list_new_messages()

    assert ids == ["msg-1", "msg-2"]
    assert service.messages_resource.list_args == {"userId": "me", "q": "in:inbox is:unread", "maxResults": 10}


def test_gmail_get_message_parses_headers_and_bodies() -> None:
    service = _GmailService()
    provider = GmailMailboxProvider("credentials.json", "token.json", "in:inbox", service=service)

    message = provider.get_message("msg-1")

    assert message.provider == "gmail"
    assert message.provider_message_id == "msg-1"
    assert message.from_address == "customer@example.com"
    assert message.to_addresses == ["support@example.com"]
    assert message.subject == "Cancel subscription"
    assert message.text_body == "Please cancel my subscription."
    assert message.html_body == "<p>Please cancel my subscription.</p>"


def test_gmail_send_reply_encodes_mime_message() -> None:
    service = _GmailService()
    provider = GmailMailboxProvider("credentials.json", "token.json", "in:inbox", service=service)
    original = provider.get_message("msg-1")

    sent = provider.send_reply(original, "Your subscription cancellation request was received.")

    assert sent.provider_message_id == "sent-1"
    raw = service.messages_resource.send_args["body"]["raw"]
    decoded = base64.urlsafe_b64decode(raw.encode())
    email = message_from_bytes(decoded, policy=default)
    assert email["To"] == "customer@example.com"
    assert email["Subject"] == "Re: Cancel subscription"
    assert email.get_content().strip() == "Your subscription cancellation request was received."


def test_gmail_mark_processed_removes_unread_label() -> None:
    service = _GmailService()
    provider = GmailMailboxProvider("credentials.json", "token.json", "in:inbox", service=service)

    provider.mark_processed("msg-1")

    assert service.messages_resource.modify_args == {
        "userId": "me",
        "id": "msg-1",
        "body": {"removeLabelIds": ["UNREAD"]},
    }

