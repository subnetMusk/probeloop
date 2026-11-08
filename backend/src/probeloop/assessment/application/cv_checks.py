"""Deterministic CV diagnostics. Counts and chronology flags are not automatic deductions."""

from __future__ import annotations

import re
from itertools import pairwise

from probeloop.assessment.domain.model import Check, Evidence
from probeloop.context.domain.model import Document

DATE_RANGE = re.compile(r"\b((?:19|20)\d{2})\s*[-\u2013]\s*((?:19|20)\d{2})\b")
NUMBER = re.compile(
    r"\b\d+(?:[.,]\d+)?\s*(?:%|ore\b|hours?\b|minuti\b|minutes?\b|utenti\b|users?\b|"
    r"ordini\b|orders?\b|test\b|consegne\b|deliveries\b|euro\b|EUR\b|USD\b|€|\$|km\b)",
    re.I,
)
EMAIL = re.compile(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b")
SECTIONS = {
    "experience": (
        r"^(?:esperienz[ae](?: professionali?| lavorative?)?|experience|work experience)$"
    ),
    "education": r"^(?:formazione|istruzione|education|studi|education and training)$",
    "skills": r"^(?:competenze(?: tecniche)?|skills|technical skills)$",
}


def cv_checks(document: Document, language: str) -> tuple[Check, ...]:
    it = language == "it"
    text = document.text

    def evidence(quote: str) -> tuple[Evidence, ...]:
        return (Evidence(document.id, quote),)

    checks = [
        Check(
            "text",
            "pass",
            ("Caratteri estratti: " if it else "Extracted characters: ") + str(len(text)),
        )
    ]
    if document.warnings:
        checks.append(Check("extraction_warnings", "review", "; ".join(document.warnings)))
    checks.append(
        Check(
            "contact",
            "pass" if EMAIL.search(text) else "review",
            (
                "Indirizzo email rilevato; recapito non verificato."
                if it
                else "Email-like text detected; contact ownership not verified."
            )
            if EMAIL.search(text)
            else (
                "Email non rilevata nel testo; verificare se il CV è anonimo."
                if it
                else "No email-like text detected; check whether this CV is anonymised."
            ),
        )
    )
    for name, pattern in SECTIONS.items():
        found = re.search(pattern, text, flags=re.I | re.M)
        checks.append(
            Check(
                f"section_{name}",
                "pass" if found else "review",
                ("Intestazione riconosciuta: " if it else "Recognised heading: ") + name
                if found
                else (
                    "Intestazione non riconosciuta; il contenuto potrebbe essere presente: "
                    if it
                    else "Heading not recognised; content may still be present: "
                )
                + name,
                evidence(found.group()) if found else (),
            )
        )
    measures = list(NUMBER.finditer(text))
    checks.append(
        Check(
            "quantification",
            "info",
            (
                "Misure numeriche di risultato o portata rilevate: "
                if it
                else "Numerical outcome or scope measures detected: "
            )
            + str(len(measures)),
            tuple(Evidence(document.id, m.group()) for m in measures[:5]),
        )
    )
    intervals = []
    for match in DATE_RANGE.finditer(text):
        start, end = int(match[1]), int(match[2])
        if end < start:
            checks.append(
                Check(
                    "date_reversed",
                    "review",
                    "Intervallo con fine prima dell'inizio."
                    if it
                    else "Date range ends before it starts.",
                    evidence(match.group()),
                )
            )
        else:
            intervals.append((start, end, match.group()))
    ordered = sorted(intervals)
    for previous, current in pairwise(ordered):
        if current[0] > previous[1] + 1:
            checks.append(
                Check(
                    "date_gap",
                    "info",
                    "Intervallo tra periodi dichiarati; non è una penalità."
                    if it
                    else "Gap between stated periods; this is not a deduction.",
                    evidence(previous[2]) + evidence(current[2]),
                )
            )
        elif current[0] < previous[1]:
            checks.append(
                Check(
                    "date_overlap",
                    "info",
                    "Intervalli annuali sovrapposti; verificare il contesto e la precisione."
                    if it
                    else "Year ranges intersect; check context and date precision.",
                    evidence(previous[2]) + evidence(current[2]),
                )
            )
    checks.append(
        Check(
            "visual_layout",
            "not_assessable",
            "Font, margini, colonne e paginazione non valutabili dal solo testo."
            if it
            else "Fonts, margins, columns and pagination cannot be rated from text alone.",
        )
    )
    links = re.findall(r"https?://[^\s<>]+", text)
    checks.append(
        Check(
            "links",
            "not_assessable",
            (
                "Link rilevati, senza verifica online: "
                if it
                else "Links detected, without network verification: "
            )
            + str(len(links)),
        )
    )
    return tuple(checks)
