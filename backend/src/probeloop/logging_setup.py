"""Structured JSON logging. Log calls must never include CV text, answers or prompts."""

from __future__ import annotations

import json
import logging
import sys
import time

# `color_message` is uvicorn's ANSI-coloured copy of the message.
_STANDARD = set(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {
    "message",
    "asctime",
    "color_message",
}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        payload.update({k: v for k, v in record.__dict__.items() if k not in _STANDARD})
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class RedactSignInCallback(logging.Filter):
    """Remove the query of the sign-in callback, which carries an authorization code, from
    uvicorn's access log."""

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if (
            isinstance(args, tuple)
            and len(args) >= 3
            and isinstance(args[2], str)
            and args[2].startswith("/auth/callback?")
        ):
            record.args = (*args[:2], "/auth/callback?[redacted]", *args[3:])
        return True


_REDACT = RedactSignInCallback()


def configure(level: str) -> None:
    logging.getLogger("uvicorn.access").addFilter(_REDACT)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())
