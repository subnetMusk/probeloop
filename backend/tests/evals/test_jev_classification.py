import json
from collections.abc import Sequence
from pathlib import Path

import pytest
from evals.jev_classification import (
    MIXED,
    cv_items,
    evaluate,
    load,
    obligation_report,
    offer_items,
    precision_recall,
)

from probeloop.context.application.ports import (
    Classified,
    LineReading,
    ObligationReading,
    OfferLine,
)
from probeloop.context.domain.model import Obligation

OFFER = """PagaFacile S.p.A. - Backend Developer, team Pagamenti

Requisiti
- Almeno tre anni di esperienza come sviluppatore backend.
- Esperienza con basi dati relazionali (preferibilmente PostgreSQL).

Gradito
- Esperienza nel dominio dei pagamenti.
"""
REQUIREMENTS = [
    {"id": "o.r1", "quote": "Almeno tre anni di esperienza", "obligation": "must"},
    {"id": "o.r2", "quote": "basi dati relazionali", "obligation": "must"},
    {"id": "o.r3", "quote": "preferibilmente PostgreSQL", "obligation": "preferred"},
    {"id": "o.r4", "quote": "dominio dei pagamenti", "obligation": "preferred"},
    {"id": "o.r5", "quote": "Italiano", "obligation": "unclear", "implicit": True},
]
CV = """Esperienze:
Ho ridotto il p95 da 1,4 s a 380 ms.
Python, FastAPI
"""
CV_LABELS = {
    "sections": [{"text": "Esperienze:", "type": "experience", "artefact": False}],
    "quantities": [{"text": "da 1,4 s a 380 ms", "kind": "outcome"}],
}


def test_offer_lines_carry_their_heading_and_one_gold_obligation() -> None:
    items = offer_items("o", OFFER, REQUIREMENTS)
    assert [(i.line.heading, i.gold) for i in items] == [
        ("Requisiti", "must"),
        ("Requisiti", MIXED),
        ("Gradito", "preferred"),
    ]
    with pytest.raises(ValueError, match=r"o\.r9"):
        offer_items("o", OFFER, [{"id": "o.r9", "quote": "Kubernetes", "obligation": "must"}])


def test_cv_lines_are_labelled_from_quantities_and_headings() -> None:
    items = cv_items("c", CV, CV_LABELS)
    assert [(i.quantified, i.heading) for i in items] == [
        (False, True),
        (True, False),
        (False, False),
    ]


def test_metrics_report_errors_per_class() -> None:
    assert precision_recall([True, True, False, False], [True, False, True, False]) == {
        "support": 2,
        "precision": 0.5,
        "recall": 0.5,
        "f1": 0.5,
    }
    report = obligation_report(["must", "preferred", MIXED], ["must", "unclear", "unclear"])
    assert report["per_class"]["preferred"]["recall"] == 0.0
    assert report["mixed_left_unclear"] == 1


class Scripted:
    """A classifier that reads the cue words, standing in for Jev."""

    async def obligations(self, lines: Sequence[OfferLine]) -> Classified[ObligationReading]:
        readings = []
        for line in lines:
            must = 0.9 if line.heading == "Requisiti" else 0.1
            preferred = 0.9 if "preferibilmente" in line.text or line.heading == "Gradito" else 0.1
            unclear = must >= 0.5 and preferred >= 0.5
            obligation = (
                Obligation.UNCLEAR
                if unclear
                else Obligation.MUST
                if must >= 0.5
                else Obligation.PREFERRED
            )
            readings.append(ObligationReading(obligation, must, preferred))
        return Classified(tuple(readings), "scripted:obligation")

    async def quantified(self, lines: Sequence[str]) -> Classified[LineReading]:
        return Classified(
            tuple(LineReading(" ms" in line, 0.8 if " ms" in line else 0.2) for line in lines),
            "scripted:quantified",
        )

    async def headings(self, lines: Sequence[str]) -> Classified[LineReading]:
        return Classified(tuple(LineReading(True, 0.6) for _ in lines), "scripted:heading")


async def test_evaluation_compares_the_classifier_with_the_labels(tmp_path: Path) -> None:
    (tmp_path / "offers").mkdir()
    (tmp_path / "cvs").mkdir()
    (tmp_path / "offers" / "o.txt").write_text(OFFER)
    (tmp_path / "cvs" / "c.txt").write_text(CV)
    labels = {
        "version": 1,
        "status": "draft",
        "offers": {"o": {"requirements": REQUIREMENTS}},
        "cvs": {"c": CV_LABELS},
    }
    (tmp_path / "labels.json").write_text(json.dumps(labels))
    with pytest.raises(SystemExit, match="not frozen"):
        load(tmp_path, allow_draft=False)

    result = await evaluate(Scripted(), tmp_path, load(tmp_path, allow_draft=True))

    assert result["model_refs"]["heading"] == "scripted:heading"
    assert result["obligation"]["per_class"]["must"] == {
        "support": 1,
        "precision": 1.0,
        "recall": 1.0,
        "f1": 1.0,
    }
    assert result["obligation"]["mixed_left_unclear"] == 1
    assert result["quantified"]["at_threshold"]["recall"] == 1.0
    assert result["heading"]["at_threshold"]["precision"] == round(1 / 3, 3)
    assert result["heading"]["sweep"]["0.7"]["recall"] == 0.0
    assert len(result["items"]["heading"]) == 3


def test_quotes_across_line_breaks_cover_every_line_they_touch() -> None:
    offer = "Nice to have\n- Experience with testing in Vitest\n  or Jest.\n"
    items = offer_items(
        "o",
        offer,
        [{"id": "o.r1", "quote": "testing in Vitest or Jest", "obligation": "preferred"}],
    )
    assert [(i.line.text, i.line.heading) for i in items] == [
        ("- Experience with testing in Vitest or Jest.", "Nice to have")
    ]
    cv = "Reduced handover time by 15\n%.\nBLS certified.\n"
    lines = cv_items("c", cv, {"quantities": [{"text": "by 15 %"}], "sections": []})
    assert [(i.line, i.quantified) for i in lines] == [
        ("Reduced handover time by 15 %.", True),
        ("BLS certified.", False),
    ]
