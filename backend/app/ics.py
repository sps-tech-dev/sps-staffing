"""RFC 5545 .ics generation (B.8) — pure functions, no calendar-provider API.

Hand-rolled VCALENDAR/VEVENT (no new dependency): UID stable per interview,
SEQUENCE bumped on every reschedule so calendar clients treat the fresh file as
an update to the same event, DTSTART/DTEND in UTC. Attached to email later via
SES (B.10); until then it's a staff download.
"""
from __future__ import annotations

import datetime as dt

from .config import settings

CRLF = "\r\n"


def _utc(ts: dt.datetime) -> str:
    return ts.astimezone(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _esc(text: str) -> str:
    """RFC 5545 TEXT escaping: backslash, semicolon, comma, newline."""
    return (text.replace("\\", "\\\\").replace(";", "\\;")
                .replace(",", "\\,").replace("\n", "\\n"))


def build_ics(*, interview_id, sequence: int, start: dt.datetime, end: dt.datetime,
              candidate_name: str, job_title: str | None = None,
              mode: str = "video", interviewer_name: str | None = None,
              candidate_email: str | None = None) -> str:
    """One VEVENT for an interview. UID is stable across reschedules; SEQUENCE
    increments — that pair is what makes calendar clients update in place."""
    now = dt.datetime.now(dt.timezone.utc)
    summary = _esc(f"Interview — {candidate_name}" + (f" ({job_title})" if job_title else ""))
    desc_bits = [f"Mode: {mode}"]
    if interviewer_name:
        desc_bits.append(f"Interviewer: {interviewer_name}")
    description = _esc(" | ".join(desc_bits))
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//SPS Technosoft//Staffing//EN",
        "METHOD:REQUEST",
        "BEGIN:VEVENT",
        f"UID:interview-{interview_id}@{settings.app_base_domain}",
        f"SEQUENCE:{sequence}",
        f"DTSTAMP:{_utc(now)}",
        f"DTSTART:{_utc(start)}",
        f"DTEND:{_utc(end)}",
        f"SUMMARY:{summary}",
        f"DESCRIPTION:{description}",
        f"ORGANIZER;CN=SPS Technosoft:mailto:info@{settings.app_base_domain}",
    ]
    if candidate_email:
        lines.append(f"ATTENDEE;CN={_esc(candidate_name)};ROLE=REQ-PARTICIPANT:"
                     f"mailto:{candidate_email}")
    lines += ["STATUS:CONFIRMED", "END:VEVENT", "END:VCALENDAR"]
    return CRLF.join(lines) + CRLF
