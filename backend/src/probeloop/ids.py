"""Identifiers: UUIDv7 written as 32 hex characters, so they sort by creation time (ADR 0004)."""

from __future__ import annotations

import secrets
import time


def new_id() -> str:
    millis = time.time_ns() // 1_000_000
    value = (millis & ((1 << 48) - 1)) << 80
    value |= 0x7 << 76  # version
    value |= secrets.randbits(12) << 64
    value |= 0b10 << 62  # variant
    value |= secrets.randbits(62)
    return f"{value:032x}"
