import base64
from datetime import datetime, timezone
from email.message import EmailMessage as MIMEEmailMessage
from email.utils import getaddresses, parseaddr
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from app.mailbox.base import MailboxProvider
from app.schemas import MailboxMessage, SentMessage


SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
]


class GmailMailboxProvider(MailboxProvider):
    name = "gmail"

    def __init__(
        self,
        credentials_file: str,
        token_file: str,
        query: str,
        max_results: int = 20,
        subject_prefix: str = "",
        auth_browser: str = "",
        service: Any | None = None,
    ) -> None:
        self.credentials_file = Path(credentials_file)
        self.token_file = Path(token_file)
        self.query = query
        self.max_results = max_results
        self.subject_prefix = subject_prefix
        self.auth_browser = auth_browser
        self.service = service or build("gmail", "v1", credentials=self._load_credentials())

    def list_new_messages(self) -> list[str]:
        response = (
            self.service.users()
            .messages()
            .list(userId="me", q=self.query, maxResults=max(self.max_results, 10))
            .execute()
        )
        message_ids: list[str] = []
        for message in response.get("messages", []):
            message_id = message["id"]
            if self._message_subject_matches(message_id):
                message_ids.append(message_id)
            if len(message_ids) >= self.max_results:
                break
        return message_ids

    def get_message(self, provider_message_id: str) -> MailboxMessage:
        payload = (
            self.service.users()
            .messages()
            .get(userId="me", id=provider_message_id, format="full")
            .execute()
        )
        headers = _headers_by_name(payload.get("payload", {}).get("headers", []))
        text_body, html_body = _extract_bodies(payload.get("payload", {}))
        from_address = parseaddr(headers.get("from", ""))[1]
        to_addresses = [address for _, address in getaddresses([headers.get("to", "")]) if address]

        return MailboxMessage(
            provider=self.name,
            provider_message_id=provider_message_id,
            from_address=from_address,
            to_addresses=to_addresses,
            subject=headers.get("subject", ""),
            text_body=text_body,
            html_body=html_body,
            received_at=_internal_date(payload.get("internalDate")),
        )

    def send_reply(self, original: MailboxMessage, body: str) -> SentMessage:
        message = MIMEEmailMessage()
        message["To"] = original.from_address
        message["Subject"] = _reply_subject(original.subject)
        message.set_content(body)
        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

        response = (
            self.service.users()
            .messages()
            .send(userId="me", body={"raw": encoded_message})
            .execute()
        )
        return SentMessage(provider_message_id=response.get("id", ""))

    def mark_processed(self, provider_message_id: str) -> None:
        (
            self.service.users()
            .messages()
            .modify(userId="me", id=provider_message_id, body={"removeLabelIds": ["UNREAD"]})
            .execute()
        )

    def _message_subject_matches(self, provider_message_id: str) -> bool:
        if not self.subject_prefix:
            return True
        payload = (
            self.service.users()
            .messages()
            .get(userId="me", id=provider_message_id, format="metadata", metadataHeaders=["Subject"])
            .execute()
        )
        headers = _headers_by_name(payload.get("payload", {}).get("headers", []))
        return headers.get("subject", "").startswith(self.subject_prefix)

    def _load_credentials(self) -> Credentials:
        credentials = None
        if self.token_file.exists():
            credentials = Credentials.from_authorized_user_file(str(self.token_file), SCOPES)

        if credentials and credentials.valid:
            return credentials

        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            if not self.credentials_file.exists():
                raise FileNotFoundError(f"Gmail credentials file not found: {self.credentials_file}")
            flow = InstalledAppFlow.from_client_secrets_file(str(self.credentials_file), SCOPES)
            credentials = flow.run_local_server(port=0, browser=(self.auth_browser or None))

        self.token_file.write_text(credentials.to_json(), encoding="utf-8")
        return credentials


def _headers_by_name(headers: list[dict[str, str]]) -> dict[str, str]:
    return {header.get("name", "").lower(): header.get("value", "") for header in headers}


def _extract_bodies(payload: dict[str, Any]) -> tuple[str, str]:
    text_parts: list[str] = []
    html_parts: list[str] = []

    def visit(part: dict[str, Any]) -> None:
        mime_type = part.get("mimeType", "")
        body = part.get("body", {})
        data = body.get("data")
        if data and mime_type == "text/plain":
            text_parts.append(_decode_body(data))
        elif data and mime_type == "text/html":
            html_parts.append(_decode_body(data))

        for child in part.get("parts", []) or []:
            visit(child)

    visit(payload)
    return "\n".join(text_parts).strip(), "\n".join(html_parts).strip()


def _decode_body(data: str) -> str:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(f"{data}{padding}".encode()).decode("utf-8", errors="replace")


def _internal_date(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)


def _reply_subject(subject: str) -> str:
    if subject.lower().startswith("re:"):
        return subject
    return f"Re: {subject}" if subject else "Re: Your support request"
