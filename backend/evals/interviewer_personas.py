"""Interviewer evaluation with scripted candidate personas, against a real model.

Runs complete simulated interviews (simulated clock, scripted answers) and checks the M2
thresholds: near-duplicate questions <= 5%, interview language 100%, one question per turn >= 90%,
and an interview length between 100% and 115% of the target.

    python -m evals.interviewer_personas --out /data/evals/interviewer.json

Exit code 1 when a threshold is missed. All answers are synthetic.
"""

from __future__ import annotations

import argparse
import asyncio
import itertools
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rapidfuzz import fuzz

from probeloop.ai.ollama import OllamaChatModel
from probeloop.interview.application.catalog import default_context
from probeloop.interview.application.events import SessionEvent
from probeloop.interview.application.llm_interviewer import LlmInterviewer
from probeloop.interview.application.orchestrator import SessionOrchestrator
from probeloop.interview.application.ports import SessionSummary
from probeloop.interview.domain.model import (
    Difficulty,
    InterviewConfig,
    InterviewerTurn,
    InterviewSession,
    InterviewType,
    Language,
    MoveAction,
)

DUPLICATE_SIMILARITY = 85
THRESHOLDS = {"duplicate_rate_max": 0.05, "language_rate_min": 1.0, "one_question_rate_min": 0.9}

# A turn with no question mark still counts as one question when it is a single formal request
# ("Mi descriva un progetto..."). `one_question_rate` keeps the strict question-mark count.
REQUEST = re.compile(
    r"\b(parli|descriva|racconti|spieghi|dica|illustri|indichi|presenti|faccia)\b", re.IGNORECASE
)


def single_request(text: str) -> bool:
    marks = text.count("?")
    return marks == 1 or (marks == 0 and bool(REQUEST.search(text)))


ITALIAN_WORDS = set(
    [
        "che",
        "di",
        "il",
        "la",
        "le",
        "lo",
        "per",
        "non",
        "è",
        "un",
        "una",
        "mi",
        "lei",
        "come",
        "del",
        "della",
        "dei",
        "delle",
        "e",
        "in",
        "con",
        "su",
        "ha",
        "ho",
        "si",
        "ci",
        "al",
        "alla",
        "questo",
        "questa",
        "sua",
        "suo",
        "può",
        "grazie",
        "molto",
        "anche",
        "quale",
        "quali",
        "cosa",
    ]
)

PERSONAS: dict[str, list[str]] = {
    "solid": [
        "Buongiorno. Sono uno sviluppatore backend con tre anni di esperienza, soprattutto con "
        "Python e FastAPI. Mi interessa questa posizione perché lavorate su problemi di logistica "
        "reali, simili a quelli che ho affrontato con il servizio di ottimizzazione dei percorsi.",
        "Il servizio riceveva gli ordini del giorno e calcolava i giri dei furgoni con OR-Tools. "
        "Io ho progettato l'API e la cache delle matrici delle distanze in Redis, mentre "
        "l'algoritmo l'aveva impostato un collega. Il tempo medio di pianificazione è sceso da "
        "quaranta a cinque minuti.",
        "Partirei da EXPLAIN ANALYZE per capire dove la query perde tempo, poi valuterei un indice "
        "mirato sulle colonne dei filtri, sapendo che ogni indice ha un costo sulle scritture.",
        "Separo test unitari, con pytest e dei fake per le dipendenze esterne, dai test di "
        "integrazione che usano un vero PostgreSQL in un container durante la CI.",
        "Una volta il team voleva introdurre Kafka. Io ero contrario perché il volume di messaggi "
        "non lo giustificava: ho preparato una stima dei costi e un prototipo con una coda più "
        "semplice, e alla fine il team ha scelto quella soluzione.",
        "Ho scelto di sacrificare un po' di freschezza dei dati a favore della velocità, mettendo "
        "una scadenza di un'ora alla cache. Per gli indirizzi modificati facevamo l'invalidazione "
        "esplicita.",
        "Sì, vorrei sapere come è organizzato il team e come lavorate in caso di incidenti.",
    ],
    "vague": [
        "Mah, cerco una nuova sfida e la vostra azienda mi sembra interessante.",
        "Sì, ho lavorato su vari progetti, diciamo che facevo un po' di tutto.",
        "Di solito si guarda la query e si cerca di ottimizzarla, dipende.",
        "I test li faccio, quando c'è tempo.",
        "Con i colleghi mi trovo bene, non ci sono mai stati problemi particolari.",
        "Non saprei, non mi è mai capitato.",
        "No, nessuna domanda.",
    ],
    "off_topic": [
        "Prima di iniziare, posso chiedere se lavorate da remoto e quanti giorni di ferie ci sono?",
        "Il progetto era interessante, ma parliamo dello stipendio: qual è la fascia prevista?",
        "Le query le ottimizzo, comunque nel weekend faccio molto trekking, sa?",
        "I test sono importanti. A proposito, avete buoni pasto?",
        "Una volta ho discusso con un collega, ma era per il calcio, non per il lavoro.",
        "Sinceramente preferirei parlare dei benefit aziendali.",
        "Sì: com'è la mensa?",
    ],
}


@dataclass
class SimClock:
    t: float = 0.0

    def now(self) -> float:
        return self.t


@dataclass
class MemoryStore:
    sessions: dict[str, InterviewSession] = field(default_factory=dict)

    async def save(self, session: InterviewSession) -> None:
        self.sessions[session.id] = session

    async def load(self, session_id: str) -> InterviewSession | None:
        return self.sessions.get(session_id)

    async def summaries(self) -> list[SessionSummary]:
        return []

    async def delete(self, session_id: str) -> bool:
        return self.sessions.pop(session_id, None) is not None


async def _ignore(event: SessionEvent) -> None:
    return None


def italian_ratio(text: str) -> float:
    words = re.findall(r"[\wàèéìòù']+", text.lower())
    return sum(w in ITALIAN_WORDS for w in words) / max(len(words), 1)


async def run_persona(
    name: str, answers: list[str], model: OllamaChatModel, minutes: int, answer_s: float
) -> dict[str, Any]:
    clock = SimClock()
    session = InterviewSession(
        id=f"{name:0<32}"[:32],
        config=InterviewConfig(
            interview_type=InterviewType.TECHNICAL,
            difficulty=Difficulty.MEDIUM,
            language=Language.ITALIAN,
            target_duration_s=minutes * 60,
        ),
        context=default_context(InterviewType.TECHNICAL),
        created_at=0.0,
    )
    orchestrator = SessionOrchestrator(
        session, interviewer=LlmInterviewer(model), store=MemoryStore(), clock=clock, sink=_ignore
    )
    await orchestrator.start()
    await orchestrator.wait_for_move()
    for answer in itertools.cycle(answers):
        if session.is_terminal:
            break
        await orchestrator.playback_finished()
        if session.is_terminal:
            break
        await orchestrator.start_answer()
        clock.t += answer_s
        await orchestrator.end_answer(answer)
        await orchestrator.wait_for_move()

    moves = [t.move for t in session.turns if isinstance(t, InterviewerTurn)]
    questions = [m.utterance for m in moves if m.action is not MoveAction.END]
    duplicates = sum(
        1
        for i, q in enumerate(questions)
        if any(fuzz.token_set_ratio(q, p) >= DUPLICATE_SIMILARITY for p in questions[:i])
    )
    ratio = session.elapsed_s(clock.now()) / session.config.target_duration_s
    return {
        "persona": name,
        "status": session.status.value,
        "end_reason": session.end_reason.value if session.end_reason else None,
        "length_ratio": round(ratio, 3),
        "moves": len(moves),
        "fallbacks": sum(m.fallback for m in moves),
        "duplicate_rate": round(duplicates / max(len(questions), 1), 3),
        "language_rate": round(
            sum(italian_ratio(m.utterance) >= 0.15 for m in moves) / max(len(moves), 1), 3
        ),
        "one_question_rate": round(
            sum(q.count("?") == 1 for q in questions) / max(len(questions), 1), 3
        ),
        "single_request_rate": round(
            sum(single_request(q) for q in questions) / max(len(questions), 1), 3
        ),
        "multi_question_turns": sum(q.count("?") > 1 for q in questions),
        "under_60_words_rate": round(
            sum(len(m.utterance.split()) <= 60 for m in moves) / max(len(moves), 1), 3
        ),
        "transcript": [
            {
                "speaker": t.speaker.value,
                "text": t.move.utterance if isinstance(t, InterviewerTurn) else t.text,
            }
            for t in session.turns
        ],
    }


def verdict(results: list[dict[str, Any]]) -> dict[str, bool]:
    return {
        "duplicates": all(r["duplicate_rate"] <= THRESHOLDS["duplicate_rate_max"] for r in results),
        "language": all(r["language_rate"] >= THRESHOLDS["language_rate_min"] for r in results),
        "one_question": all(
            r["single_request_rate"] >= THRESHOLDS["one_question_rate_min"] for r in results
        ),
        "length": all(r["status"] == "ended" and 1.0 <= r["length_ratio"] <= 1.15 for r in results),
    }


async def main_async(args: argparse.Namespace) -> int:
    model = OllamaChatModel(
        base_url=os.environ.get("PROBELOOP_OLLAMA_BASE_URL", "http://host.docker.internal:11434"),
        model=args.model,
        context_window=8192,
    )
    results = [
        await run_persona(name, answers, model, args.minutes, args.answer_seconds)
        for name, answers in PERSONAS.items()
    ]
    report = {
        "model": model.model_ref,
        "thresholds": THRESHOLDS,
        "verdict": verdict(results),
        "results": results,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    summary = {k: v for k, v in report.items() if k != "results"}
    summary["personas"] = [{k: v for k, v in r.items() if k != "transcript"} for r in results]
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if all(report["verdict"].values()) else 1


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model", default=os.environ.get("PROBELOOP_INTERVIEWER_MODEL", "ministral-3:8b")
    )
    parser.add_argument("--minutes", type=int, default=15)
    parser.add_argument("--answer-seconds", type=float, default=90.0)
    parser.add_argument("--out", type=Path, default=Path("/data/evals/interviewer.json"))
    sys.exit(asyncio.run(main_async(parser.parse_args())))


if __name__ == "__main__":
    main()
