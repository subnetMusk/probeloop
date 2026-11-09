"""Presentation conversion; judges and calibration retain their descriptive 1-5 anchors."""

from __future__ import annotations


def score_100(value: float | None) -> float | None:
    # Preserve precision in JSON for lossless persistence; reading surfaces round to integers.
    return None if value is None else round((value - 1) * 25, 8)


def anchored_score(value: float | None) -> float | None:
    return None if value is None else round(value / 25 + 1, 8)
