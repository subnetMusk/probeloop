import copy
import json
from pathlib import Path
from typing import Any

from evals.cv_check_labels import found, problems

OFFER = "Requisiti\n- Almeno tre anni di esperienza backend.\n\nGradito\n- Conoscenza di Kafka.\n"
CV = (
    "Esperienze\n2019 - 2024 Backend developer.\n"
    "Ho introdotto Kafka per gli\naggiornamenti di stato.\n"
)
REQUIREMENT = {
    "id": "o.r1",
    "quote": "Almeno tre anni di esperienza backend",
    "category": "experience",
    "obligation": "must",
    "cue": "Requisiti",
    "any_of": None,
    "equivalents": None,
    "threshold": {"kind": "years", "min": 3, "subject": "backend"},
    "refines": None,
    "implicit": False,
}
PREFERRED = {
    **REQUIREMENT,
    "id": "o.r2",
    "quote": "Conoscenza di Kafka",
    "category": "skill",
    "obligation": "preferred",
    "cue": "Gradito",
    "threshold": None,
}
PAIR = {
    "target_level": "mid",
    "fit_band": "strong",
    "rewrite_traps": [],
    "requirements": {
        "o.r1": {
            "coverage": "direct",
            "evidence": [
                {
                    "quote": "2019 - 2024 Backend developer",
                    "relation": "applied",
                    "specificity": "context",
                }
            ],
            "years": {"count": 5, "intervals": ["2019 - 2024"], "precision": "year"},
            "note": "Five years from the CV's dates.",
        },
        "o.r2": {
            "coverage": "direct",
            "evidence": [
                {
                    "quote": "Ho introdotto Kafka per gli aggiornamenti di stato",
                    "relation": "applied",
                    "specificity": "context",
                }
            ],
            "years": None,
            "note": "Kafka introduced in a role.",
        },
    },
}


def write(tmp_path: Path, labels: dict[str, Any]) -> Path:
    (tmp_path / "offers").mkdir(exist_ok=True)
    (tmp_path / "cvs").mkdir(exist_ok=True)
    (tmp_path / "offers" / "o.txt").write_text(OFFER)
    (tmp_path / "cvs" / "c.txt").write_text(CV)
    (tmp_path / "cvs" / "c--headings.txt").write_text(CV.replace("Esperienze", "PERCORSO"))
    pairs = [
        {"id": "p1", "cv": "c", "offer": "o", "language": "it", "variant_of": None},
        {"id": "v1", "cv": "c--headings", "offer": "o", "language": "it", "variant_of": "p1"},
    ]
    (tmp_path / "pairs.json").write_text(json.dumps({"pairs": pairs}))
    (tmp_path / "labels.json").write_text(json.dumps(labels))
    return tmp_path


def valid() -> dict[str, Any]:
    cv = {
        "sections": [{"text": "Esperienze", "type": "experience", "artefact": False}],
        "dates": [{"text": "2019 - 2024", "start": "2019", "end": "2024", "precision": "year"}],
        "quantities": [],
        "artefacts": [],
        "defects": [],
    }
    variant = copy.deepcopy(cv)
    variant["sections"][0]["text"] = "PERCORSO"
    return {
        "version": 1,
        "status": "draft",
        "reference_date": "2026-11-12",
        "offers": {"o": {"requirements": [REQUIREMENT, PREFERRED]}},
        "cvs": {"c": cv, "c--headings": variant},
        "pairs": {"p1": PAIR, "v1": copy.deepcopy(PAIR)},
        "review": [],
        "changes": [],
    }


def test_quotes_match_across_case_and_line_breaks() -> None:
    assert found("introdotto kafka per gli aggiornamenti", CV)
    assert not found("introdotto Kafka in produzione", CV)
    assert not found("  ", CV)


def test_valid_labels_have_no_problems(tmp_path: Path) -> None:
    assert problems(write(tmp_path, valid())) == []


def test_errors_are_reported_with_their_place(tmp_path: Path) -> None:
    labels = valid()
    labels["offers"]["o"]["requirements"][0]["quote"] = "Almeno cinque anni di esperienza"
    labels["offers"]["o"]["requirements"][1]["obligation"] = "nice"
    labels["pairs"]["p1"]["requirements"]["o.r2"]["coverage"] = "insufficient"
    labels["pairs"]["v1"]["requirements"]["o.r1"]["coverage"] = "partial"
    labels["pairs"]["v1"]["requirements"]["o.r1"]["evidence"][0]["quote"] = "Kafka in produzione"
    del labels["cvs"]["c--headings"]

    found_problems = problems(write(tmp_path, labels))

    assert "o/o.r1: quote not found in the offer" in found_problems
    assert "o/o.r2: unknown obligation 'nice'" in found_problems
    assert "p1/o.r2: insufficient coverage has no evidence" in found_problems
    assert "v1/o.r1: coverage differs from its base pair" in found_problems
    assert "v1/o.r1: quote 'Kafka in produzione' not found in the CV" in found_problems
    assert "c--headings: CV without labels" in found_problems
