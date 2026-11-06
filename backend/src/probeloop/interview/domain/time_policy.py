"""Time policy: how much of the interview remains and what the interviewer must do about it.

The LLM decides how to spend time across topics. This policy only enforces the limits.
"""

from __future__ import annotations

from enum import StrEnum

WRAP_UP_AT = 0.85
FINAL_QUESTION_AT = 1.0
FORCE_CLOSE_AT = 1.15


class TimeDirective(StrEnum):
    NORMAL = "normal"
    BEGIN_WRAP_UP = "begin_wrap_up"
    FINAL_QUESTION = "final_question"
    CLOSE = "close"
    FORCE_CLOSE = "force_close"


def time_directive(
    elapsed_s: float, target_s: float, *, final_question_asked: bool
) -> TimeDirective:
    """Return the directive for the next interviewer move.

    `FORCE_CLOSE` means the orchestrator closes without the LLM. `CLOSE` means the next move must
    end the interview, because the final question has already been asked.
    """
    ratio = elapsed_s / target_s
    if ratio >= FORCE_CLOSE_AT:
        return TimeDirective.FORCE_CLOSE
    if final_question_asked:
        return TimeDirective.CLOSE
    if ratio >= FINAL_QUESTION_AT:
        return TimeDirective.FINAL_QUESTION
    if ratio >= WRAP_UP_AT:
        return TimeDirective.BEGIN_WRAP_UP
    return TimeDirective.NORMAL


def remaining_s(elapsed_s: float, target_s: float) -> float:
    return max(0.0, target_s - elapsed_s)
