"""Probe the CV check with synthetic material and scripted models; no real model is called.

Each section prints how one step of the current pipeline treats a crafted input, so that its
behaviour can be compared with the CV rating requirements. The output is deterministic.

    python -m evals.cv_check_probe
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from probeloop.ai.fake import FakeChatModel
from probeloop.assessment.application.cv_checks import DATE_RANGE, cv_checks
from probeloop.assessment.application.cv_review import CvReviewer
from probeloop.assessment.application.evidence import Source, checked_judgements
from probeloop.assessment.application.rubrics import load_rubric
from probeloop.assessment.application.schemas import JudgementsOut
from probeloop.assessment.domain.model import overall_score
from probeloop.context.application.analysis import (
    ContextAnalyser,
    FactOut,
    MatchingOut,
    checked_matches,
)
from probeloop.context.application.snapshots import job_brief
from probeloop.context.domain.model import (
    ContextSnapshot,
    Document,
    DocumentKind,
    DocumentOrigin,
    Fact,
    FactKind,
    FactOrigin,
    JobMode,
    MatchStatus,
    RequirementMatch,
    RoleProfile,
    Subject,
)

FIXTURES = Path(__file__).parent / "fixtures/synthetic/context/acceptance"
CV = (FIXTURES / "cv-marco-galli.txt").read_text()
OFFER = (FIXTURES / "offer-pagafacile-backend.txt").read_text()
RUBRIC = load_rubric("cv")


def document(text: str, kind: DocumentKind = DocumentKind.CV, id: str = "cv") -> Document:
    return Document(id, kind, "Synthetic", DocumentOrigin.TYPED, text, 0)


def heading(title: str) -> None:
    print(f"\n=== {title}")


def deterministic_checks(label: str, text: str) -> None:
    ranges = [m.group() for m in DATE_RANGE.finditer(text)]
    print(f"-- {label}: year ranges read = {ranges}")
    for check in cv_checks(document(text), "en"):
        if check.id.startswith(("section_", "date_")) or check.id == "quantification":
            quotes = [e.quote for e in check.evidence]
            print(f"   {check.id}: {check.status} | {check.detail} | {quotes}")


def document_checks() -> None:
    heading("1. Deterministic checks on cv-marco-galli.txt and common variants")
    variants = {
        "as written": CV,
        "heading with a colon": CV.replace("\nEsperienze\n", "\nEsperienze:\n"),
        "English upper-case heading": CV.replace("\nEsperienze\n", "\nPROFESSIONAL EXPERIENCE\n"),
        "Work history": CV.replace("\nEsperienze\n", "\nWork history\n"),
        "letter-spaced extraction": CV.replace("\nEsperienze\n", "\nE S P E R I E N Z E\n"),
        "projects heading": CV.replace("\nEsperienze\n", "\nProgetti\n"),
        "month-year ranges": CV.replace("2022 - oggi", "03/2022 - oggi")
        .replace("2019 - 2022", "09/2019 - 02/2022")
        .replace("2018 - 2019", "01/2018 - 08/2019"),
    }
    for label, text in variants.items():
        deterministic_checks(label, text)


def requirement_extraction() -> None:
    heading("2. Requirement extraction: stored kind for offer statements")
    analyser = ContextAnalyser(FakeChatModel(["{}"]))
    offer = document(OFFER, DocumentKind.JOB_OFFER, "offer")
    items = [
        ("skill", "Conoscenza di sistemi a eventi"),
        ("requirement", "Buona conoscenza di Python o di un altro linguaggio backend"),
        ("requirement", "Esperienza con basi dati relazionali (preferibilmente PostgreSQL)"),
    ]
    for kind, statement in items:
        fact = analyser._fact(
            offer, FactOut(subject="job", kind=kind, statement=statement, quote=statement)
        )
        print(f"   model kind {kind!r} -> stored {fact.kind.value!r}: {fact.statement}")
    print(f"   fields of an extracted fact: {list(FactOut.model_fields)}")


REQUIRED = Fact(
    "r1",
    Subject.JOB,
    FactKind.REQUIREMENT,
    "Conoscenza di sistemi a eventi",
    FactOrigin.DECLARED,
    "offer",
    "Conoscenza di sistemi a eventi",
)
PREFERRED = Fact(
    "r2",
    Subject.JOB,
    FactKind.NICE_TO_HAVE,
    "Esperienza nel dominio dei pagamenti",
    FactOrigin.DECLARED,
    "offer",
    "Esperienza nel dominio dei pagamenti",
)
INFERRED_SKILL = Fact(
    "c1", Subject.CANDIDATE, FactKind.SKILL, "Usa Kafka", FactOrigin.INFERRED, "cv", None
)
ROLE = Fact(
    "c2",
    Subject.CANDIDATE,
    FactKind.ROLE,
    "Backend developer presso Trasporti Digitali dal 2022",
    FactOrigin.DECLARED,
    "cv",
    "Backend developer, Trasporti Digitali S.r.l.",
)


def requirement_matching() -> None:
    heading("3. Requirement matching after the code checks")
    out = MatchingOut.model_validate(
        {
            "matches": [
                {
                    "requirement_id": "r1",
                    "status": "partial",
                    "fact_ids": ["c1"],
                    "rationale": "Usa Kafka: copertura parziale.",
                }
            ]
        }
    )
    for match in checked_matches(out, [REQUIRED, PREFERRED], [INFERRED_SKILL, ROLE]):
        print(
            f"   {match.requirement_id}: {match.status.value} facts={match.fact_ids} "
            f"rationale={match.rationale!r}"
        )


def snapshot(text: str, role: RoleProfile | None) -> ContextSnapshot:
    return ContextSnapshot(
        id="s",
        preparation_id="p",
        created_at=0,
        language="it",
        job_mode=JobMode.OFFER,
        candidate_facts=(ROLE,),
        job_facts=(REQUIRED, PREFERRED),
        matches=(
            RequirementMatch("r1", MatchStatus.MET, ("c2",), "Kafka in produzione."),
            RequirementMatch("r2", MatchStatus.NOT_SHOWN),
        ),
        area=None,
        vocabulary=(),
        documents=(document(text), document(OFFER, DocumentKind.JOB_OFFER, "offer")),
        content_hash="h",
        role_profile=role,
    )


CONFIRMED_ROLE = RoleProfile(
    "Software engineering",
    "Backend developer",
    "mid",
    ("API",),
    ("Python",),
    ("r1", "r2"),
    "",
    True,
)


def target_brief() -> None:
    heading("4. Target data given to the CV reviewer (job_brief)")
    for label, role in (
        ("without a role profile", None),
        ("with a confirmed role", CONFIRMED_ROLE),
    ):
        print(f"-- {label}:")
        print("   " + job_brief(snapshot(CV, role)).replace("\n", "\n   "))


def evidence_and_rewrites() -> None:
    heading("5. Evidence and rewrite checks (checked_judgements)")
    skills = "Python, FastAPI, Django, SQLAlchemy, PostgreSQL"
    output = JudgementsOut.model_validate(
        {
            "scores": [
                {
                    "criterion_id": criterion.id,
                    "score": 5,
                    "reason": "Strong.",
                    "evidence": [{"source_id": "cv", "quote": skills}],
                }
                for criterion in RUBRIC.criteria
            ],
            "observations": [
                {
                    "kind": "rewrite",
                    "text": "Show leadership.",
                    "evidence": [
                        {
                            "source_id": "cv",
                            "quote": "Affianco due sviluppatori junior nelle revisioni del codice.",
                        }
                    ],
                    "replacement": "Ho guidato il team backend e gestito Kubernetes in produzione.",
                },
                {
                    "kind": "rewrite",
                    "text": "State the scale.",
                    "evidence": [
                        {
                            "source_id": "cv",
                            "quote": "Integrazione con tre corrieri tramite API REST e SOAP.",
                        }
                    ],
                    "replacement": "Integrazione con dodici corrieri internazionali via REST.",
                },
                {
                    "kind": "improvement",
                    "text": "Add metrics to every bullet.",
                    "evidence": [{"source_id": "cv", "quote": skills}],
                },
            ],
        }
    )
    scores, notes, dropped = checked_judgements(output, RUBRIC, {"cv": Source(CV)}, language="it")
    assessed = sum(score.value is not None for score in scores)
    print(f"   criteria scored 5 from one skills-list quote: {assessed}/{len(scores)}")
    for note in notes:
        print(f"   kept {note.kind}: {note.replacement or note.text}")
    print(f"   dropped: {dropped}")


def answer(fit: int, reason: str, quote: str) -> str:
    scores: dict[str, Any] = {
        criterion.id: {
            "evidence": [{"source_id": "cv", "quote": quote}],
            "reason": reason,
            "score": fit if criterion.id in ("relevance", "depth") else 4,
        }
        for criterion in RUBRIC.criteria
    }
    observation = {
        "kind": "improvement",
        "text": "Quantify outcomes.",
        "evidence": [{"source_id": "cv", "quote": quote}],
        "replacement": None,
    }
    return json.dumps({"scores": scores, "observations": [observation]})


async def passage_aggregation() -> None:
    heading("6. CV review over several passages (scripted model)")
    projects = "\n\n".join(
        f"Progetto personale {i}: script di automazione per la contabilita' domestica."
        for i in range(60)
    )
    model = FakeChatModel(
        [
            answer(
                5, "Strong evidence for the target.", "Ho introdotto Kafka per gli aggiornamenti"
            ),
            answer(
                1, "Little evidence for the target here.", "script di automazione per la contab"
            ),
        ]
    )

    async def progress(value: float, message: str | None) -> None:
        return None

    scores, notes, _, _ = await CvReviewer(model, RUBRIC).review(
        snapshot(f"{CV}\n\n{projects}", CONFIRMED_ROLE), "en", progress
    )
    print(f"   passages judged: {len(model.requests)}")
    for score in scores:
        if score.criterion_id in ("relevance", "depth"):
            print(f"   {score.criterion_id}: {score.value} reason={score.reason!r}")
    print(f"   observations: {[note.text for note in notes]}")
    print(f"   overall over seven equally weighted criteria: {overall_score(scores)}")


if __name__ == "__main__":
    document_checks()
    requirement_extraction()
    requirement_matching()
    target_brief()
    evidence_and_rewrites()
    asyncio.run(passage_aggregation())
