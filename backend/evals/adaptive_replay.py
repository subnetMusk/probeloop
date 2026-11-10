"""Repeat assessment of audited, frozen synthetic sessions without changing their reports."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from copy import deepcopy
from dataclasses import asdict, replace
from pathlib import Path
from statistics import mean
from typing import Any

from probeloop.ai.ports import ChatMessage, ChatRequest
from probeloop.assessment.application.interview_review import InterviewReviewer
from probeloop.bootstrap import build
from probeloop.context.domain.model import ContextSnapshot
from probeloop.interview.domain.model import InterviewSession, RevisionSource, TranscriptRevision
from probeloop.settings import Settings
from probeloop.storage.session_files import atomic_write

QUALITY_TRAITS = {
    "strong": "Explain the economic distinction accurately, including assumptions and limits.",
    "weak": "Make one substantive conceptual error in the economic explanation. "
    "Maintain it as your belief, without announcing that it is an error.",
    # An intermediate answer checks whether the judge separates partial from full quality.
    "partial": "Use an appropriate method and reach an approximately correct conclusion, but "
    "leave one relevant assumption or limitation unexamined and state one detail imprecisely. "
    "Do not make a gross conceptual error and do not announce the omission.",
}


def fingerprint(session: InterviewSession, snapshot: ContextSnapshot | None) -> str:
    payload = {
        "context": asdict(session.context),
        "config": asdict(session.config),
        "turns": [asdict(turn) for turn in session.turns],
        "snapshot": snapshot.content_hash if snapshot else None,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def validate_audit(audit: dict[str, Any], session: InterviewSession, digest: str) -> dict[str, Any]:
    entry = audit.get("sessions", {}).get(session.id, {})
    if (
        audit.get("synthetic") is not True
        or entry.get("fingerprint") != digest
        or entry.get("persona_coherent") is not True
        or not entry.get("sources")
    ):
        raise ValueError("an exact source-audited synthetic input is required")
    return dict(entry)


def replay_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    profiles = {}
    for profile in sorted({row["profile"] for row in rows}):
        selected = [r for r in rows if r["profile"] == profile]
        groups: dict[str, list[dict[str, Any]]] = {}
        for row in selected:
            groups.setdefault(row["session_id"], []).append(row)
        spreads = {
            key: max(r["mean"] for r in group) - min(r["mean"] for r in group)
            if all(r["mean"] is not None for r in group)
            else None
            for key, group in groups.items()
        }
        weak = [r for r in selected if r.get("quality") == "weak"]
        detected = [
            r
            for r in weak
            if any(
                s["criterion_id"] == "technical.accuracy"
                and s["value"] is not None
                and s["value"] <= 2
                for s in r["judgement"]["scores"]
            )
            or any(n["kind"] == "technical_error" for n in r["judgement"]["observations"])
        ]
        pairs = []
        for strong in (r for r in selected if r.get("quality") == "strong"):
            other = next(
                (
                    r
                    for r in weak
                    if r.get("pair_id") == strong.get("pair_id")
                    and r["regeneration"] == strong["regeneration"]
                ),
                None,
            )
            if other:
                pairs.append(
                    strong["mean"] is not None
                    and other["mean"] is not None
                    and strong["mean"] > other["mean"]
                )
        profiles[profile] = {
            "reviews": len(selected),
            "repeats": {k: len(v) for k, v in groups.items()},
            "detection": len(detected) / len(weak) if weak else None,
            "ranking": sum(pairs) / len(pairs) if pairs else None,
            "spreads": spreads,
            "max_mean_spread": max((v for v in spreads.values() if v is not None), default=None),
            "unverified": sum(r["unverified"] for r in selected)
            if all("unverified" in r for r in selected)
            else None,
            "strong_corrections": sum(
                n["kind"] == "technical_error"
                for r in selected
                if r.get("quality") == "strong"
                for n in r["judgement"]["observations"]
            ),
        }
    return {
        "profiles": profiles,
        "scope": "Assessment replay only; does not establish adaptive conversation acceptance.",
    }


async def progress(_fraction: float, _message: str | None) -> None:
    pass


def paired_session(source: InterviewSession, quality: str, text: str) -> InterviewSession:
    """Keep a first-question contrast separate from whole-conversation acceptance."""
    variant = deepcopy(source)
    variant.id = hashlib.sha256(f"{source.id}:{quality}:{text}".encode()).hexdigest()[:32]
    question, answer = source.interviewer_turns()[0], source.candidate_turns()[0]
    variant.turns = [
        question,
        replace(
            answer, revisions=(TranscriptRevision(1, text, RevisionSource.USER_EDIT, answer.at),)
        ),
    ]
    return variant


async def run(args: argparse.Namespace) -> None:
    services = build(Settings())
    rows: list[dict[str, Any]] = []
    try:
        sessions = []
        pair = json.loads(args.pair_inputs.read_text()) if args.pair_inputs else None
        source_ids = [pair["source_session"]] if pair else args.session
        for session_id in source_ids:
            session = await services.store.load(session_id)
            if session is None or not session.is_terminal or not session.context.policy_version:
                raise ValueError("a terminal adaptive session is required")
            snapshot = (
                await services.context.snapshot(session.snapshot_id)
                if session.snapshot_id
                else None
            )
            sessions.append((session, snapshot, fingerprint(session, snapshot)))
        if args.generate_pair:
            source, _, _ = sessions[0]
            question = source.interviewer_turns()[0].move.utterance
            model = services.roles["interviewer"].pinned("cloud")
            answers = {}
            for quality in args.quality or ["strong", "weak"]:
                traits = QUALITY_TRAITS[quality]
                result = await model.complete(
                    ChatRequest(
                        instructions=(
                            "A synthetic candidate answers this actual question in English. "
                            "one spoken paragraph of 55-90 words. No invented personal history or "
                            "citations. " + traits
                        ),
                        messages=(
                            ChatMessage(
                                "user",
                                json.dumps(
                                    {
                                        "role": asdict(source.context.role_profile)
                                        if source.context.role_profile
                                        else None,
                                        "question": question,
                                    }
                                ),
                            ),
                        ),
                        max_output_tokens=350,
                    )
                )
                answers[quality] = result.text.strip()
            if args.output.exists():
                raise ValueError("preserve previous generated inputs")
            atomic_write(
                args.output,
                json.dumps(
                    {
                        "source_session": source.id,
                        "question": question,
                        "candidate_model": model.model_ref,
                        "answers": answers,
                    },
                    ensure_ascii=False,
                    indent=2,
                ).encode(),
            )
            return
        if pair:
            source, snapshot, _ = sessions[0]
            if pair["question"] != source.interviewer_turns()[0].move.utterance:
                raise ValueError("source question changed")
            sessions = []
            for quality, text in pair["answers"].items():
                variant = paired_session(source, quality, text)
                sessions.append((variant, snapshot, fingerprint(variant, snapshot)))
        if args.describe:
            print(json.dumps({s.id: digest for s, _, digest in sessions}), flush=True)
            return
        audit = json.loads(args.audit.read_text())
        for session, _, digest in sessions:
            validate_audit(audit, session, digest)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        if args.output.exists():
            raise ValueError("output exists; preserve previous measurements")
        for profile in args.profile:
            reviewer = InterviewReviewer(services.roles["evaluation"].pinned(profile))
            if reviewer.model.model_ref.startswith("fake"):
                raise ValueError("live calibration requires a real evaluator")
            for session, snapshot, digest in sessions:
                for n in range(args.regenerations):
                    judgement = await reviewer.review(
                        session, snapshot, session.config.language.value, progress
                    )
                    values = [s.value for s in judgement.scores if s.value is not None]
                    row = {
                        "profile": profile,
                        "model": reviewer.model.model_ref,
                        "prompt_ref": reviewer.prompt_ref_for(session),
                        "session_id": session.id,
                        "quality": audit["sessions"][session.id].get("quality"),
                        "pair_id": audit["sessions"][session.id].get("pair_id"),
                        "fingerprint": digest,
                        "regeneration": n + 1,
                        "mean": mean(values) if values else None,
                        "judgement": asdict(judgement),
                    }
                    texts = {turn.seq: turn.text for turn in session.candidate_turns()}
                    scored = (*judgement.scores, *judgement.unit_scores)
                    quoted = [
                        *(e for s in scored for e in s.evidence),
                        *(e for o in judgement.observations for e in o.evidence),
                    ]
                    row["unverified"] = sum(
                        evidence.turn_seq is None
                        or evidence.quote not in texts.get(evidence.turn_seq, "")
                        for evidence in quoted
                    )
                    rows.append(row)
                    atomic_write(
                        args.output, json.dumps(rows, ensure_ascii=False, indent=2).encode()
                    )
                    print(f"DONE {profile} {session.id} {n + 1} mean={row['mean']}", flush=True)
        atomic_write(
            args.output.with_suffix(".summary.json"),
            json.dumps(replay_metrics(rows), indent=2).encode(),
        )
    finally:
        await services.engine.dispose()
        await services.data.close()
        services.extractor.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", action="append", default=[])
    parser.add_argument(
        "--generate-pair",
        action="store_true",
        help="controlled response variants to a real recorded question",
    )
    parser.add_argument("--pair-inputs", type=Path)
    parser.add_argument(
        "--quality", action="append", choices=sorted(QUALITY_TRAITS), help="generated variants"
    )
    parser.add_argument("--profile", action="append", choices=["local", "cloud"], default=[])
    parser.add_argument("--regenerations", type=int, default=5)
    parser.add_argument("--describe", action="store_true")
    parser.add_argument("--audit", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not args.session and not args.pair_inputs:
        parser.error("a source session or frozen pair inputs are required")
    if args.generate_pair and (len(args.session) != 1 or not args.output):
        parser.error("pair generation requires one source session and a new output path")
    if (
        not args.describe
        and not args.generate_pair
        and (not args.audit or not args.output or not args.profile)
    ):
        parser.error("assessment requires audit, output and at least one profile")
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
