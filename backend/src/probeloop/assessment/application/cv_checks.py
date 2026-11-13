"""Deterministic CV diagnostics. Counts and chronology flags are not automatic deductions.

When a line classifier is selected, it reads which logical lines are section headings and which
state a measured outcome or scope; rules still decide which section a heading names. Without its
readings, exact patterns find the headings and the measures.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from itertools import pairwise

from probeloop.assessment.domain.model import Check, Evidence
from probeloop.context.application.ports import Classified, LineReading
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
# The wordings of a heading the classifier has found, compared by their letters alone.
HEADINGS = {
    "experience": (
        "esperienza",
        "esperienze",
        "esperienza professionale",
        "esperienze professionali",
        "esperienza lavorativa",
        "esperienze lavorative",
        "percorso professionale",
        "carriera",
        "progetti",
        "progetti principali",
        "experience",
        "work experience",
        "professional experience",
        "employment",
        "employment history",
        "work history",
        "career history",
        "career",
        "projects",
        "key projects",
        "selected projects",
    ),
    "education": (
        "formazione",
        "istruzione",
        "istruzione e formazione",
        "formazione e istruzione",
        "studi",
        "titoli di studio",
        "percorso di studi",
        "percorso formativo",
        "education",
        "education and training",
        "education & training",
        "academic background",
        "training",
    ),
    "skills": (
        "competenze",
        "competenze tecniche",
        "competenze professionali",
        "competenze informatiche",
        "competenze digitali",
        "competenze chiave",
        "capacità e competenze",
        "conoscenze",
        "conoscenze tecniche",
        "conoscenze informatiche",
        "abilità",
        "skills",
        "technical skills",
        "key skills",
        "core skills",
        "hard skills",
        "skills and competencies",
        "competencies",
        "core competencies",
        "tech stack",
        "stack tecnologico",
    ),
}


def heading_key(line: str) -> str:
    """The letters of a heading in lower case, so `E S P E R I E N Z A:` reads `esperienza`."""
    return "".join(c for c in line.casefold() if c.isalpha())


_SECTION_OF = {heading_key(w): name for name, words in HEADINGS.items() for w in words}


@dataclass(frozen=True, slots=True)
class LineReadings:
    """The logical lines of a CV and the classifier's heading and measured-outcome readings."""

    lines: tuple[str, ...]
    headings: Classified[LineReading]
    quantified: Classified[LineReading]

    def read(self, classified: Classified[LineReading]) -> list[str]:
        """The lines that `classified` reads as positive, in order."""
        pairs = zip(self.lines, classified.readings, strict=True)
        return [line for line, reading in pairs if reading.positive]


def cv_checks(
    document: Document, language: str, lines: LineReadings | None = None
) -> tuple[Check, ...]:
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
    headings = _matched_headings(text) if lines is None else _read_headings(lines)
    for name in SECTIONS:
        found = headings.get(name)
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
                evidence(found) if found else (),
            )
        )
    if lines is None:
        measures = [m.group() for m in NUMBER.finditer(text)]
        counted = (
            "Misure numeriche di risultato o portata rilevate: "
            if it
            else "Numerical outcome or scope measures detected: "
        )
    else:
        measures = lines.read(lines.quantified)
        counted = (
            "Righe con un risultato o una portata misurati: "
            if it
            else "Lines stating a measured outcome or scope: "
        )
    checks.append(
        Check(
            "quantification",
            "info",
            counted + str(len(measures)),
            tuple(Evidence(document.id, m) for m in measures[:5]),
        )
    )
    if lines is not None:
        checks.append(
            Check(
                "line_reader",
                "info",
                (
                    "Intestazioni e risultati misurati letti dal classificatore di righe; "
                    "le sezioni sono riconosciute da regole. Modelli: "
                    if it
                    else "Headings and measured outcomes read by the line classifier; "
                    "sections are recognised by rules. Models: "
                )
                + "; ".join(dict.fromkeys((lines.headings.model_ref, lines.quantified.model_ref))),
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


def _matched_headings(text: str) -> dict[str, str]:
    """The first heading of each section that its exact pattern matches."""
    found = {}
    for name, pattern in SECTIONS.items():
        match = re.search(pattern, text, flags=re.I | re.M)
        if match:
            found[name] = match.group()
    return found


def _read_headings(lines: LineReadings) -> dict[str, str]:
    """The first line the classifier reads as a heading for each section the rules name."""
    found: dict[str, str] = {}
    for line in lines.read(lines.headings):
        section = _SECTION_OF.get(heading_key(line))
        if section is not None:
            found.setdefault(section, line)
    return found
