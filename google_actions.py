# google_actions.py — Gmail + Calendar + Timer integration

from __future__ import annotations

import base64
import datetime as dt
import threading
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Callable, Optional
from zoneinfo import ZoneInfo

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/gmail.send",
]


class GoogleActions:
    """Handles Google API actions: Gmail, Calendar, and local timers."""

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

        # Active timers: name -> threading.Timer
        self._timers: dict[str, threading.Timer] = {}

        self._load_credentials()

    # ─────────────────────────────────────────── Auth ────

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
                        f"Missing {self.credentials_file}. Download your OAuth 2.0 client "
                        "JSON from Google Cloud Console → APIs & Services → Credentials "
                        "and save it here."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self.credentials_file),
                    SCOPES,
                )
                try:
                    creds = flow.run_local_server(port=0)
                except Exception:
                    # Headless / Raspberry Pi fallback
                    creds = flow.run_console()

            self.token_file.write_text(creds.to_json())

        self._creds = creds

    # ─────────────────────────────────────────── Services ────

    @property
    def calendar(self):
        if self._calendar_service is None:
            self._calendar_service = build(
                "calendar", "v3", credentials=self._creds, cache_discovery=False
            )
        return self._calendar_service

    @property
    def gmail(self):
        if self._gmail_service is None:
            self._gmail_service = build(
                "gmail", "v1", credentials=self._creds, cache_discovery=False
            )
        return self._gmail_service

    # ─────────────────────────────────────────── Gmail ────

    def send_email(
        self,
        to: str,
        subject: str,
        body_text: str,
        cc: Optional[str] = None,
        bcc: Optional[str] = None,
        body_html: Optional[str] = None,
    ) -> dict:
        """Send an email via Gmail.

        Args:
            to: Recipient address.
            subject: Email subject.
            body_text: Plain-text body (always included).
            cc: Optional CC address.
            bcc: Optional BCC address.
            body_html: Optional HTML body for a multipart message.

        Returns:
            dict with ``id``, ``threadId``, and ``labelIds``.
        """
        if body_html:
            message: MIMEMultipart | MIMEText = MIMEMultipart("alternative")
            message.attach(MIMEText(body_text, "plain"))
            message.attach(MIMEText(body_html, "html"))
        else:
            message = MIMEText(body_text)

        message["to"] = to
        message["subject"] = subject
        if cc:
            message["cc"] = cc
        if bcc:
            message["bcc"] = bcc

        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

        sent = (
            self.gmail.users()
            .messages()
            .send(userId="me", body={"raw": raw_message})
            .execute()
        )

        return {
            "id": sent.get("id"),
            "threadId": sent.get("threadId"),
            "labelIds": sent.get("labelIds", []),
        }

    # ─────────────────────────────────────────── Calendar ────

    def create_calendar_event(
        self,
        summary: str,
        start_iso: str,
        end_iso: str,
        description: str = "",
        location: str = "",
    ) -> dict:
        """Create a Google Calendar event on the primary calendar.

        Args:
            summary: Title of the event.
            start_iso: ISO-8601 start datetime string (e.g. ``"2025-06-01T14:00:00"``).
            end_iso: ISO-8601 end datetime string.
            description: Optional event description / notes.
            location: Optional location string.

        Returns:
            dict with ``id``, ``summary``, ``htmlLink``, ``start``, ``end``.
        """
        event_body: dict = {
            "summary": summary,
            "description": description,
            "start": {"dateTime": start_iso, "timeZone": str(self.timezone)},
            "end": {"dateTime": end_iso, "timeZone": str(self.timezone)},
        }
        if location:
            event_body["location"] = location

        created = (
            self.calendar.events()
            .insert(calendarId="primary", body=event_body)
            .execute()
        )

        return {
            "id": created.get("id"),
            "summary": created.get("summary"),
            "htmlLink": created.get("htmlLink"),
            "start": created.get("start", {}),
            "end": created.get("end", {}),
        }

    def list_today_events(self) -> list[dict]:
        """Return a list of today's calendar events (primary calendar)."""
        now = dt.datetime.now(self.timezone)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        start_of_next_day = start_of_day + dt.timedelta(days=1)

        result = (
            self.calendar.events()
            .list(
                calendarId="primary",
                timeMin=start_of_day.isoformat(),
                timeMax=start_of_next_day.isoformat(),
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        output = []
        for item in result.get("items", []):
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

    # ─────────────────────────────────────────── Timers ────

    def set_timer(
        self,
        label: str,
        seconds: float,
        on_fire: Optional[Callable[[str], None]] = None,
    ) -> str:
        """Set a countdown timer.

        Args:
            label: Human-readable name (e.g. ``"pasta timer"``).
            seconds: Duration in seconds.
            on_fire: Optional callback called with ``label`` when the timer fires.
                     If ``None``, a log message is printed.

        Returns:
            Confirmation string describing the timer.
        """
        # Cancel any existing timer with the same label
        self._cancel_timer(label)

        def _fire():
            print(f"⏰ [TIMER FIRED] '{label}' is done!")
            if on_fire:
                on_fire(label)
            # Clean up reference
            self._timers.pop(label, None)

        t = threading.Timer(seconds, _fire)
        t.daemon = True
        t.start()
        self._timers[label] = t

        minutes, secs = divmod(int(seconds), 60)
        hours, minutes = divmod(minutes, 60)
        human = _format_duration(hours, minutes, secs)
        return f"Timer '{label}' set for {human}."

    def cancel_timer(self, label: str) -> str:
        """Cancel an active timer by label.

        Returns:
            Confirmation string.
        """
        if self._cancel_timer(label):
            return f"Timer '{label}' cancelled."
        return f"No active timer named '{label}' found."

    def list_timers(self) -> list[str]:
        """Return the labels of all currently active timers."""
        return list(self._timers.keys())

    def _cancel_timer(self, label: str) -> bool:
        t = self._timers.pop(label, None)
        if t:
            t.cancel()
            return True
        return False


# ─────────────────────────────────────────── helpers ────

def _format_duration(hours: int, minutes: int, seconds: int) -> str:
    parts = []
    if hours:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    if seconds or not parts:
        parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")
    return " and ".join(parts)