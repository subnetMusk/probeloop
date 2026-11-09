import pytest
from pydantic import ValidationError

from probeloop.assessment.application.schemas import unit_output


def test_numeric_judgement_requires_evidence_in_the_adaptive_schema() -> None:
    output = unit_output(("reasoning",), observations=False, elicitation=True)
    with pytest.raises(ValidationError):
        output.model_validate(
            {"scores": {"reasoning": {"evidence": [], "reason": "Reason", "score": 3}}}
        )
    missing = output.model_validate(
        {
            "scores": {
                "reasoning": {
                    "evidence": [{"source_id": "turn-1", "quote": "I cannot explain that method."}],
                    "reason": "Insufficient evidence",
                    "score": None,
                }
            }
        }
    )
    assert missing.model_dump()["scores"]["reasoning"]["score"] is None
    valid = output.model_validate(
        {
            "scores": {
                "reasoning": {
                    "evidence": [{"source_id": "turn-1", "quote": "I would check assumptions."}],
                    "reason": "Explains a check",
                    "score": 4,
                }
            }
        }
    )
    assert valid.model_dump()["scores"]["reasoning"]["score"] == 4
