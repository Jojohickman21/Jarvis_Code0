# google_actions.py

from __future__ import annotations

import base64
import datetime as dt
from email.mime.text import MIMEText
from pathlib import Path
from zoneinfo import ZoneInfo
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/gmail.send",
]


class GoogleActions:
    def __init__(
        self,
        credentials_file: str = "credentials.json",
        token_file: str = "token.json",
        timezone: str = "America/Los_Angeles",
    ):
        self.credentials_file = Path(credentials_file)
        self.token_file = Path(token_file)
        self.timezone = ZoneInfo(timezone)

        self._creds: Optional[Credentials] = None
        self._calendar_service = None
        self._gmail_service = None

        self._load_credentials()

    def _load_credentials(self) -> None:
        creds = None

        if self.token_file.exists():
            creds = Credentials.from_authorized_user_file(str(self.token_file), SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not self.credentials_file.exists():
                    raise FileNotFoundError(
                        f"Missing {self.credentials_file}. Download your OAuth client JSON "
                        "from Google Cloud and save it here."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self.credentials_file),
                    SCOPES,
                )
                try:
                    creds = flow.run_local_server(port=0)
                except Exception:
                    # Handy if the Pi is headless / no browser session is available
                    creds = flow.run_console()

            self.token_file.write_text(creds.to_json())

        self._creds = creds

    @property
    def calendar(self):
        if self._calendar_service is None:
            self._calendar_service = build(
                "calendar",
                "v3",
                credentials=self._creds,
                cache_discovery=False,
            )
        return self._calendar_service

    @property
    def gmail(self):
        if self._gmail_service is None:
            self._gmail_service = build(
                "gmail",
                "v1",
                credentials=self._creds,
                cache_discovery=False,
            )
        return self._gmail_service

    def create_calendar_event(
        self,
        summary: str,
        start_iso: str,
        end_iso: str,
        description: str = "",
    ) -> dict:
        event_body = {
            "summary": summary,
            "description": description,
            "start": {
                "dateTime": start_iso,
                "timeZone": str(self.timezone),
            },
            "end": {
                "dateTime": end_iso,
                "timeZone": str(self.timezone),
            },
        }

        created = self.calendar.events().insert(
            calendarId="primary",
            body=event_body,
        ).execute()

        return {
            "id": created.get("id"),
            "summary": created.get("summary"),
            "htmlLink": created.get("htmlLink"),
            "start": created.get("start", {}),
            "end": created.get("end", {}),
        }

    def list_today_events(self) -> list[dict]:
        now = dt.datetime.now(self.timezone)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        start_of_next_day = start_of_day + dt.timedelta(days=1)

        result = self.calendar.events().list(
            calendarId="primary",
            timeMin=start_of_day.isoformat(),
            timeMax=start_of_next_day.isoformat(),
            singleEvents=True,
            orderBy="startTime",
        ).execute()

        items = result.get("items", [])
        output = []

        for item in items:
            start_info = item.get("start", {})
            raw_start = start_info.get("dateTime") or start_info.get("date") or ""
            output.append(
                {
                    "summary": item.get("summary", "(no title)"),
                    "start": raw_start,
                    "location": item.get("location", ""),
                    "description": item.get("description", ""),
                }
            )

        return output

    def send_email(
        self,
        to: str,
        subject: str,
        body_text: str,
        cc: Optional[str] = None,
        bcc: Optional[str] = None,
    ) -> dict:
        message = MIMEText(body_text)
        message["to"] = to
        message["subject"] = subject
        if cc:
            message["cc"] = cc
        if bcc:
            message["bcc"] = bcc

        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

        sent = self.gmail.users().messages().send(
            userId="me",
            body={"raw": raw_message},
        ).execute()

        return {
            "id": sent.get("id"),
            "threadId": sent.get("threadId"),
            "labelIds": sent.get("labelIds", []),
        }