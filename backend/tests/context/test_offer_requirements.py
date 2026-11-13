from __future__ import annotations

from collections.abc import Sequence

import pytest

from probeloop.ai.fake import FakeChatModel
from probeloop.context.application.analysis import ContextAnalyser
from probeloop.context.application.ports import (
    Classified,
    LineReading,
    ObligationReading,
    OfferLine,
    TextClassifierUnavailable,
)
from probeloop.context.domain.model import JobMode, Obligation
from probeloop.context.domain.offer_cues import cue_obligation, locate
from tests.context.conftest import cv, offer, scripted_analysis

MUST, PREFERRED, UNCLEAR = Obligation.MUST, Obligation.PREFERRED, Obligation.UNCLEAR
OFFER = """Backend Developer

Requisiti
- Esperienza con basi dati relazionali (preferibilmente PostgreSQL).
- Buona conoscenza di Python o di un altro linguaggio
  backend.

Costituisce titolo preferenziale
- Certificazione CompTIA A+.
"""


def test_a_phrase_in_the_requirement_decides_before_its_heading() -> None:
    assert cue_obligation("Esperienza con basi dati relazionali", "Requisiti") == (
        MUST,
        "Requisiti",
    )
    assert cue_obligation("preferibilmente PostgreSQL", "Requisiti") == (
        PREFERRED,
        "preferibilmente",
    )
    assert cue_obligation("È indispensabile un'esperienza di 5 anni", None) == (
        MUST,
        "indispensabile",
    )
    assert cue_obligation("Certificazione CompTIA A+", "Costituisce titolo preferenziale") == (
        PREFERRED,
        "Costituisce titolo preferenziale",
    )
    assert cue_obligation("ICU experience would be a plus", "Bonus points") == (
        PREFERRED,
        "a plus",
    )
    assert cue_obligation("Conoscenza delle WCAG 2.2", None) is None
    assert cue_obligation("Mustard production", "Cosa offriamo") is None
    # Contradictory phrases decide nothing.
    assert cue_obligation("required, ideally in Go", None) is None


def test_quotes_are_found_across_line_breaks_with_their_heading() -> None:
    assert locate(OFFER, "un altro linguaggio backend") == (
        "- Buona conoscenza di Python o di un altro linguaggio backend.",
        "Requisiti",
    )
    assert locate(OFFER, "Certificazione CompTIA A+") == (
        "- Certificazione CompTIA A+.",
        "Costituisce titolo preferenziale",
    )
    assert locate(OFFER, "Kubernetes") is None


class Scripted:
    """Reads every requirement as mandatory, and records what it was asked."""

    def __init__(self) -> None:
        self.asked: list[OfferLine] = []

    async def obligations(self, lines: Sequence[OfferLine]) -> Classified[ObligationReading]:
        self.asked += lines
        return Classified(tuple(ObligationReading(MUST, 0.9, 0.1) for _ in lines), "scripted")

    async def quantified(self, lines: Sequence[str]) -> Classified[LineReading]:
        raise AssertionError("not used by the analysis")

    async def headings(self, lines: Sequence[str]) -> Classified[LineReading]:
        raise AssertionError("not used by the analysis")


async def test_jev_reads_after_the_cue_and_before_the_model() -> None:
    jev = Scripted()
    analyser = ContextAnalyser(FakeChatModel([scripted_analysis()]), classifier=lambda: jev)

    result = await analyser.analyse([cv(), offer()], JobMode.OFFER, "it")

    details = {f.statement: f.requirement for f in result.facts if f.requirement}
    kubernetes = details["Kubernetes in produzione."]
    assert kubernetes is not None
    # The heading "Preferibile" decides; Jev's and the model's "must" stay visible.
    assert kubernetes.obligation is PREFERRED
    assert kubernetes.readings == (("cue", PREFERRED), ("jev", MUST), ("model", MUST))
    assert kubernetes.disputed
    assert [line.heading for line in jev.asked] == ["Requisiti", "Requisiti", "Preferibile"]
    assert "Italiano fluente." not in [line.text for line in jev.asked]  # implicit


async def test_a_selected_classifier_that_fails_stops_the_analysis() -> None:
    class Down(Scripted):
        async def obligations(self, lines: Sequence[OfferLine]) -> Classified[ObligationReading]:
            raise TextClassifierUnavailable(
                "Jev is unreachable; check the connection and try again"
            )

    analyser = ContextAnalyser(FakeChatModel([scripted_analysis()]), classifier=lambda: Down())
    with pytest.raises(TextClassifierUnavailable, match="unreachable"):
        await analyser.analyse([cv(), offer()], JobMode.OFFER, "it")
