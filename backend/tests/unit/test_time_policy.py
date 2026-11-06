from __future__ import annotations

import pytest

from probeloop.interview.domain.time_policy import TimeDirective, remaining_s, time_directive

TARGET = 900.0


@pytest.mark.parametrize(
    ("elapsed", "final_asked", "expected"),
    [
        (0, False, TimeDirective.NORMAL),
        (764, False, TimeDirective.NORMAL),
        (765, False, TimeDirective.BEGIN_WRAP_UP),
        (899, False, TimeDirective.BEGIN_WRAP_UP),
        (900, False, TimeDirective.FINAL_QUESTION),
        (950, True, TimeDirective.CLOSE),
        (1034, True, TimeDirective.CLOSE),
        (1035, False, TimeDirective.FORCE_CLOSE),
        (1035, True, TimeDirective.FORCE_CLOSE),
    ],
)
def test_directive_thresholds(elapsed: float, final_asked: bool, expected: TimeDirective) -> None:
    assert time_directive(elapsed, TARGET, final_question_asked=final_asked) is expected


def test_remaining_never_negative() -> None:
    assert remaining_s(100, TARGET) == 800
    assert remaining_s(1200, TARGET) == 0
