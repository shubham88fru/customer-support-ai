from datetime import datetime
from typing import Any

import httpx

from app.mailbox.base import MailboxProvider, MailboxSendBlockedError, MailboxSendError
from app.schemas import MailboxMessage, SentMessage


class MailSlurpMailboxProvider(MailboxProvider):
    name = "mailslurp"
    base_url = "https://api.mailslurp.com"

    def __init__(self, api_key: str, inbox_id: str) -> None:
        if not api_key:
            raise ValueError("MAILSLURP_API_KEY is required when MAILBOX_PROVIDER=mailslurp")
        if not inbox_id:
            raise ValueError("MAILSLURP_INBOX_ID is required when MAILBOX_PROVIDER=mailslurp")
        self.api_key = api_key
        self.inbox_id = inbox_id
        self.client = httpx.Client(
            base_url=self.base_url,
            headers={"x-api-key": api_key},
            timeout=30,
        )

    def list_new_messages(self) -> list[str]:
        response = self.client.get(f"/inboxes/{self.inbox_id}/emails", params={"size": 20, "sort": "DESC"})
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict) and "content" in payload:
            emails = payload["content"]
        else:
            emails = payload
        return [str(email["id"]) for email in emails if "id" in email]

    def get_message(self, provider_message_id: str) -> MailboxMessage:
        response = self.client.get(f"/emails/{provider_message_id}")
        response.raise_for_status()
        email = response.json()
        return MailboxMessage(
            provider=self.name,
            provider_message_id=str(email["id"]),
            from_address=email.get("from") or "",
            to_addresses=_as_list(email.get("to")),
            subject=email.get("subject") or "",
            text_body=email.get("body") or email.get("text") or "",
            html_body=email.get("html") or "",
            received_at=_parse_datetime(email.get("createdAt")),
        )

    def send_reply(self, original: MailboxMessage, body: str) -> SentMessage:
        payload = {
            "to": [original.from_address],
            "subject": _reply_subject(original.subject),
            "body": body,
            "isHTML": False,
        }
        response = self.client.post(f"/inboxes/{self.inbox_id}/confirm", json=payload)
        _raise_for_status(response, "send reply")
        sent = response.json()
        return SentMessage(provider_message_id=str(sent.get("id") or sent.get("messageId") or ""))

    def mark_processed(self, provider_message_id: str) -> None:
        # MailSlurp messages are left in the inbox. Local deduplication prevents repeated processing.
        return None


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _reply_subject(subject: str) -> str:
    if subject.lower().startswith("re:"):
        return subject
    return f"Re: {subject}" if subject else "Re: Your support request"


def _raise_for_status(response: httpx.Response, action: str) -> None:
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        body = response.text[:1000]
        message = (
            f"MailSlurp {action} failed: status={response.status_code} "
            f"url={response.request.method} {response.request.url} body={body}"
        )
        if _is_send_blocked(response):
            raise MailboxSendBlockedError(message) from exc
        raise MailboxSendError(message) from exc


def _is_send_blocked(response: httpx.Response) -> bool:
    if response.status_code != 429:
        return False
    try:
        payload = response.json()
    except ValueError:
        return False
    return payload.get("errorCode") == "W_429_SEND_BLOCK_TRIAL" or payload.get("errorClass") == "Error429SendingBlocked"
