"""Names and headers of the files the API sends for download or display."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from urllib.parse import quote

type DownloadSubject = Literal["interview", "cv-check"]


def file_headers(filename: str, *, inline: bool) -> dict[str, str]:
    """Download headers with an ASCII fallback name and the UTF-8 name (RFC 6266 and 5987)."""
    fallback = "".join(
        c if c.isascii() and c.isprintable() and c not in '"\\' else "_" for c in filename
    )
    disposition = "inline" if inline else "attachment"
    return {
        "Content-Disposition": (
            f"{disposition}; filename=\"{fallback}\"; filename*=UTF-8''{quote(filename)}"
        ),
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "private, no-cache",
    }


def subject_filename(
    subject: DownloadSubject, subject_id: str, created_at: float, artefact: str
) -> str:
    """`probeloop-<subject>-<YYYYMMDD>-<id8>-<artefact>`, dated by the subject's creation (UTC),
    so the files of different interviews and CV checks never share a name."""
    day = datetime.fromtimestamp(created_at, UTC).strftime("%Y%m%d")
    return f"probeloop-{subject}-{day}-{subject_id[:8]}-{artefact}"


def timestamped_filename(stem: str, now: float, extension: str) -> str:
    """`probeloop-<stem>-<YYYYMMDD-hhmmss>.<extension>`, in UTC."""
    moment = datetime.fromtimestamp(now, UTC).strftime("%Y%m%d-%H%M%S")
    return f"probeloop-{stem}-{moment}.{extension}"
