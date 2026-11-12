"""Synthetic documents and a scripted model for the context tests."""

from __future__ import annotations

import json
from collections.abc import Callable

from probeloop.ai.ports import ChatRequest
from probeloop.context.domain.model import Document, DocumentKind, DocumentOrigin

CV_TEXT = """Giulia Neri
Backend developer

Esperienza
2021-2024 Backend developer presso Logistica Veloce: ho progettato il servizio di
ottimizzazione dei percorsi in Python con FastAPI e PostgreSQL, riducendo i km percorsi del 12%.
2018-2021 Sviluppatrice junior presso Studio Web Rossi: siti in PHP e Laravel.

Competenze
Python, FastAPI, PostgreSQL, Redis, Docker, Kubernetes di base.
"""

OFFER_TEXT = """Senior backend engineer - piattaforma di pagamenti

Requisiti
- Almeno 5 anni di esperienza con Python
- Esperienza con Kafka e architetture a eventi
- Conoscenza di PostgreSQL

Preferibile
- Esperienza con Kubernetes in produzione
"""


def document(kind: DocumentKind, text: str, doc_id: str, title: str = "doc") -> Document:
    return Document(
        id=doc_id, kind=kind, title=title, origin=DocumentOrigin.TYPED, text=text, created_at=0
    )


def cv() -> Document:
    return document(DocumentKind.CV, CV_TEXT, "cv1", "CV")


def offer() -> Document:
    return document(DocumentKind.JOB_OFFER, OFFER_TEXT, "jo1", "Offerta")


CV_FACTS = {
    "facts": [
        {
            "subject": "candidate",
            "kind": "role",
            "statement": "Backend developer presso Logistica Veloce dal 2021 al 2024.",
            "quote": "2021-2024 Backend developer presso Logistica Veloce",
        },
        {
            "subject": "candidate",
            "kind": "achievement",
            "statement": "Ha ridotto i km percorsi del 12% con il servizio di ottimizzazione.",
            "quote": "riducendo i km percorsi del 12%",
        },
        {
            "subject": "candidate",
            "kind": "skill",
            "statement": "Esperta di Kafka.",
            "quote": "Kafka in produzione per cinque anni",  # not in the CV: inferred
        },
        {
            "subject": "job",  # a CV fact is always about the candidate
            "kind": "skill",
            "statement": "Usa Python e PostgreSQL.",
            "quote": "Python, FastAPI, PostgreSQL, Redis",
        },
    ],
    "terms": ["Python", "FastAPI", "PostgreSQL", "Redis", "Terraform"],
}

OFFER_FACTS = {
    "facts": [
        {
            "subject": "job",
            "kind": "requirement",
            "statement": "Almeno 5 anni di esperienza con Python.",
            "quote": "Almeno 5 anni di esperienza con Python",
        },
        {
            "subject": "job",
            "kind": "requirement",
            "statement": "Esperienza con Kafka e architetture a eventi.",
            "quote": "Esperienza con Kafka e architetture a eventi",
        },
        {
            "subject": "job",
            "kind": "nice_to_have",
            "statement": "Kubernetes in produzione.",
            "quote": "Esperienza con Kubernetes in produzione",
        },
    ],
    "terms": ["Python", "Kafka", "Kubernetes"],
}


def requirement(statement: str, quote: str, obligation: str, **extra: object) -> dict[str, object]:
    return {
        "statement": statement,
        "quote": quote,
        "category": "experience",
        "obligation": obligation,
        "any_of": [],
        "equivalents": [],
        "threshold": None,
        "refines": None,
        "implicit": False,
    } | extra


OFFER_EXTRACTION = {
    "requirements": [
        requirement(
            "Almeno 5 anni di esperienza con Python.",
            "Almeno 5 anni di esperienza con Python",
            "must",
            threshold={"kind": "years", "minimum": "5", "subject": "Python"},
        ),
        requirement(
            "Esperienza con Kafka e architetture a eventi.",
            "Esperienza con Kafka e architetture a eventi",
            "preferred",  # the heading says it is required: the cue wins
        ),
        requirement(
            "Kubernetes in produzione.",
            "Esperienza con Kubernetes in produzione",
            "must",  # the heading says it is preferred: the cue wins
            category="skill",
        ),
        requirement(
            "Italiano fluente.",
            "",
            "unclear",
            category="language",
            implicit=True,
        ),
    ],
    "facts": [
        {
            "kind": "company",
            "statement": "Piattaforma di pagamenti.",
            "quote": "Senior backend engineer - piattaforma di pagamenti",
        }
    ],
    "terms": ["Python", "Kafka", "Kubernetes"],
}


def scripted_analysis(
    matches: Callable[[ChatRequest], dict[str, object]] | None = None,
) -> Callable[[ChatRequest], str]:
    """Answers each analysis prompt according to what it asks."""

    def answer(request: ChatRequest) -> str:
        text = request.instructions
        content = request.messages[0].content
        if "objectives" in (request.response_schema or {}).get("properties", {}):
            facts = json.loads(content)["facts"]
            ids = [f["id"] for f in facts if f["subject"] == "candidate"][:1]
            return json.dumps(
                {
                    "objectives": [
                        {
                            "title": "Il servizio di ottimizzazione dei percorsi",
                            "objective": "Explore own contribution.",
                            "rubric_kind": "technical",
                            "priority": 3,
                            "fact_ids": ids,
                            "criteria": ["experience", "ownership"],
                            "past_example": True,
                            "solvable": False,
                        },
                        {
                            "title": "Esperienza con Kafka, non mostrata",
                            "objective": "Explore reasoning without assuming experience.",
                            "rubric_kind": "technical",
                            "priority": 2,
                            "fact_ids": [],
                            "criteria": ["reasoning", "problem_solving"],
                            "past_example": False,
                            "solvable": True,
                        },
                    ]
                }
            )
        if "Propose the target professional profile" in text:
            return json.dumps(
                {
                    "profession": "Software engineering",
                    "target_role": "Backend engineer",
                    "seniority": "mid",
                    "responsibilities": ["Build reliable services"],
                    "competencies": ["Professional reasoning"],
                    "basis_fact_ids": [],
                    "rationale": "Proposal.",
                }
            )
        if "requirements of a job offer" in text:
            return json.dumps(OFFER_EXTRACTION)
        if "list the facts" in text:
            return json.dumps(OFFER_FACTS if "Offerta" in content else CV_FACTS)
        if "compare the requirements" in text:
            if matches is not None:
                return json.dumps(matches(request))
            ids = [line.split(":")[0][2:] for line in content.splitlines() if line.startswith("- ")]
            return json.dumps(
                {
                    "matches": [
                        {
                            "requirement_id": ids[0],
                            "status": "met",
                            "fact_ids": [ids[-1], "nonexistent"],
                            "rationale": "Python nel CV.",
                        },
                        {
                            "requirement_id": ids[1],
                            "status": "met",
                            "fact_ids": [],  # met without evidence: becomes not_shown
                            "rationale": "Probabile.",
                        },
                    ]
                }
            )
        if "infer the professional area" in text:
            return json.dumps(
                {"area": "sviluppo backend", "seniority": "mid", "rationale": "Ruoli backend."}
            )
        if "plausible job offer" in text:
            return json.dumps(
                {
                    "title": "Sviluppatore web junior",
                    "company": "Agenzia di siti web.",
                    "seniority": "junior",
                    "summary": "Sviluppo di siti in PHP.",
                    "responsibilities": ["Sviluppare siti"],
                    "requirements": ["PHP", "Laurea in informatica"],
                    "nice_to_have": [],
                }
            )
        if "plan the topics" in text.lower():
            return json.dumps(
                {
                    "topics": [
                        {"title": "Il servizio di ottimizzazione dei percorsi", "reason": "x"},
                        {"title": "Esperienza con Kafka, non mostrata", "reason": "x"},
                        {"title": "Candidate questions and closing", "reason": "x"},
                    ]
                }
            )
        raise AssertionError(f"unexpected prompt: {text[:80]}")

    return answer
