"""M1 spike: Ollama latency, VRAM, prefix reuse and interviewer move formats.

Throwaway code, not part of the application. Results are written to /results/llm/.

Usage (inside the bench container):
    python llm_bench.py latency --target container --model qwen3.5:9b
    python llm_bench.py moves --target container --model qwen3.5:9b --n 50
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any, Callable

import httpx
from pydantic_core import from_json

RESULTS = Path("/results/llm")
SCENARIO = json.loads(Path("/spikes/inputs/scenario_it.json").read_text(encoding="utf-8"))
BASES = {
    "container": os.environ["OLLAMA_CONTAINER_URL"],
    "native": os.environ["OLLAMA_NATIVE_URL"],
}
ACTIONS = ["follow_up", "clarify", "new_topic", "present_exercise", "wrap_up", "end"]
HEADER_RE = re.compile(
    r"^ACTION=(%s)\s+TOPIC=(t\d+)(?:\s+COVERED=(none|t\d+(?:\s*,\s*t\d+)*))?\s*$" % "|".join(ACTIONS)
)
SENTENCE_END = re.compile(r"[.?!…](?:\s|$)")
ITALIAN_WORDS = set(
    "che di il la le lo per non è un una mi lei come del della dei delle e in con su ha ho si "
    "ci al alla questo questa sua suo può grazie molto anche".split()
)
SAMPLING = {"temperature": 0.7, "top_p": 0.8, "top_k": 20}

RULES = """You are a professional recruiter conducting a spoken job interview in {language}.
Rules:
- Speak only {language}. Spoken style: no markdown, no lists, no emojis.
- Ask exactly one question per turn. Keep each turn under 60 words.
- Use only facts from the candidate brief and the transcript. Never invent facts about the candidate.
- Do not evaluate the answers or give feedback during the interview.
- Do not repeat a question already asked, unless you are asking for a clarification.
- If an answer is vague, ask for a concrete example. If it is complete, go deeper or move to an uncovered topic.
- If the candidate goes off topic, acknowledge briefly and steer back.
- Follow the time directive given in the last message.
"""

HEADER_FORMAT = """Output format:
First line, exactly: ACTION=<follow_up|clarify|new_topic|present_exercise|wrap_up|end> TOPIC=<topic id> COVERED=<comma-separated ids of topics now fully covered, or none>
From the second line on: only the words you say to the candidate."""

JSON_FORMAT = """Output a JSON object with the fields action, topic_id, utterance, covered_topic_ids, in this order.
utterance contains only the words you say to the candidate."""

MOVE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ACTIONS},
        "topic_id": {"type": "string"},
        "utterance": {"type": "string"},
        "covered_topic_ids": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["action", "topic_id", "utterance", "covered_topic_ids"],
}


# --------------------------------------------------------------------------- prompts


def header_to_json(text: str) -> str:
    header, _, utterance = text.partition("\n")
    m = HEADER_RE.match(header.strip())
    assert m, header
    covered = [] if not m.group(3) or m.group(3) == "none" else [c.strip() for c in m.group(3).split(",")]
    return json.dumps(
        {"action": m.group(1), "topic_id": m.group(2), "utterance": utterance.strip(), "covered_topic_ids": covered},
        ensure_ascii=False,
    )


def context_block() -> str:
    topics = "\n".join(f"- {t['id']}: {t['title']}" for t in SCENARIO["topics"])
    return (
        f"Job: {SCENARIO['job']}\n\nCandidate brief: {SCENARIO['candidate_brief']}\n\n"
        f"Interview topics:\n{topics}"
    )


def filler_history(target_tokens: int) -> list[tuple[str, str]]:
    """Earlier exchanges recycled from the scenario, used only to reach a prompt size."""
    pairs = [
        (s["history"][-1][1], s["answer"])
        for s in SCENARIO["states"]
        if s["history"] and s["answer"]
    ]
    out: list[tuple[str, str]] = []
    chars = 0
    i = 0
    while chars / 3.3 < target_tokens:
        question, answer = pairs[i % len(pairs)]
        out.append(("interviewer", question))
        out.append(("candidate", answer))
        chars += len(question) + len(answer)
        i += 1
    return out


def state_block(state: dict[str, Any], asked: list[str]) -> str:
    covered = ", ".join(state["covered"]) or "none"
    asked_list = "\n".join(f"- {q}" for q in asked[-12:]) or "- none"
    return (
        f"[Interview state]\nCovered topics: {covered}\n"
        f"Questions already asked:\n{asked_list}\n"
        f"Time directive: {state['directive']}"
    )


def build_messages(
    state: dict[str, Any],
    fmt: str,
    *,
    filler_tokens: int = 0,
    system_nonce: str = "",
    extra_turns: list[tuple[str, str]] | None = None,
) -> list[dict[str, str]]:
    system = system_nonce + RULES.format(language=SCENARIO["language"]) + "\n" + (
        HEADER_FORMAT if fmt == "header" else JSON_FORMAT
    )
    history = filler_history(filler_tokens) if filler_tokens else []
    history += [tuple(t) for t in state["history"]]  # type: ignore[misc]
    if state["answer"] is not None:
        history.append(("candidate", state["answer"]))
    history += extra_turns or []

    messages = [{"role": "system", "content": system}]
    first_user = context_block() + "\n\nThe interview starts now."
    asked: list[str] = []
    pending_user = first_user
    for speaker, text in history:
        if speaker == "interviewer":
            messages.append({"role": "user", "content": pending_user})
            content = header_to_json(text) if fmt == "json" and text.startswith("ACTION=") else text
            messages.append({"role": "assistant", "content": content})
            asked.append(text.partition("\n")[2] if text.startswith("ACTION=") else text)
            pending_user = ""
        else:
            pending_user = (pending_user + "\n\n" if pending_user else "") + f"Candidate: {text}"
    messages.append(
        {"role": "user", "content": (pending_user + "\n\n" if pending_user else "") + state_block(state, asked)}
    )
    return messages


# --------------------------------------------------------------------------- ollama


class Ollama:
    def __init__(self, base: str) -> None:
        self.base = base
        self.http = httpx.Client(base_url=base, timeout=900)
        self._caps: dict[str, list[str]] = {}

    def capabilities(self, model: str) -> list[str]:
        if model not in self._caps:
            r = self.http.post("/api/show", json={"model": model})
            r.raise_for_status()
            self._caps[model] = r.json().get("capabilities", [])
        return self._caps[model]

    def ps(self) -> list[dict[str, Any]]:
        r = self.http.get("/api/ps")
        r.raise_for_status()
        return [
            {
                "name": m["name"],
                "size_gb": round(m["size"] / 1e9, 2),
                "size_vram_gb": round(m.get("size_vram", 0) / 1e9, 2),
                "context_length": m.get("context_length"),
            }
            for m in r.json().get("models", [])
        ]

    def unload_all(self) -> None:
        for m in self.ps():
            self.http.post("/api/generate", json={"model": m["name"], "keep_alive": 0}).raise_for_status()
        for _ in range(60):
            if not self.ps():
                return
            time.sleep(0.5)

    def chat(
        self,
        model: str,
        messages: list[dict[str, str]],
        num_ctx: int,
        *,
        schema: dict[str, Any] | None = None,
        num_predict: int = 160,
        on_text: Callable[[str, float, dict[str, float]], None] | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": True,
            "keep_alive": "30m",
            "options": {**SAMPLING, "num_ctx": num_ctx, "num_predict": num_predict},
        }
        if "thinking" in self.capabilities(model):
            body["think"] = False
        if schema is not None:
            body["format"] = schema
        t0 = time.perf_counter()
        first: float | None = None
        text = ""
        marks: dict[str, float] = {}
        final: dict[str, Any] = {}
        with self.http.stream("POST", "/api/chat", json=body) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if not line:
                    continue
                ev = json.loads(line)
                chunk = ev.get("message", {}).get("content", "")
                if chunk:
                    now = time.perf_counter() - t0
                    if first is None:
                        first = now
                    text += chunk
                    if on_text:
                        on_text(text, now, marks)
                if ev.get("done"):
                    final = ev
                    break
        ns = 1e9
        res = {
            "ttft_s": first,
            "total_s": time.perf_counter() - t0,
            "load_s": final.get("load_duration", 0) / ns,
            "prompt_tokens": final.get("prompt_eval_count"),
            "prompt_s": final.get("prompt_eval_duration", 0) / ns,
            "eval_tokens": final.get("eval_count"),
            "eval_s": final.get("eval_duration", 0) / ns,
            "text": text,
            **marks,
        }
        if res["prompt_tokens"] and res["prompt_s"]:
            res["prefill_tps"] = res["prompt_tokens"] / res["prompt_s"]
        if res["eval_tokens"] and res["eval_s"]:
            res["gen_tps"] = res["eval_tokens"] / res["eval_s"]
        return res


def other_bases(target: str) -> list[Ollama]:
    out = []
    for name, base in BASES.items():
        if name == target:
            continue
        try:
            o = Ollama(base)
            o.ps()
            out.append(o)
        except httpx.HTTPError:
            pass
    return out


def free_gpu(target: str, client: Ollama) -> None:
    for other in other_bases(target):
        other.unload_all()
    client.unload_all()


def safe(model: str) -> str:
    return model.replace(":", "_").replace("/", "_")


def strip_text(r: dict[str, Any]) -> dict[str, Any]:
    return {k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items() if k != "text"}


# --------------------------------------------------------------------------- latency


def run_latency(target: str, model: str) -> dict[str, Any]:
    client = Ollama(BASES[target])
    free_gpu(target, client)
    opening = SCENARIO["states"][0]
    project = SCENARIO["states"][2]
    out: dict[str, Any] = {"target": target, "model": model, "capabilities": client.capabilities(model)}

    r = client.chat(model, build_messages(opening, "header"), 8192, num_predict=8)
    out["cold_8k"] = strip_text(r)
    out["ps_8k"] = client.ps()

    out["fresh_8k"] = []
    for tokens in (2000, 4000):
        msgs = build_messages(project, "header", filler_tokens=tokens, system_nonce=f"[run {uuid.uuid4()}]\n")
        out["fresh_8k"].append({"target_tokens": tokens, **strip_text(client.chat(model, msgs, 8192, num_predict=120))})

    base = build_messages(project, "header", filler_tokens=4000, system_nonce="[run fixed]\n")
    r1 = client.chat(model, base, 8192, num_predict=120)
    appended = build_messages(
        project,
        "header",
        filler_tokens=4000,
        system_nonce="[run fixed]\n",
        extra_turns=[("interviewer", r1["text"] if r1["text"].startswith("ACTION=") else
                      "ACTION=follow_up TOPIC=t2 COVERED=t1\n" + r1["text"]),
                     ("candidate", "Sì, la cache aveva una scadenza di un'ora e la invalidavamo quando cambiavano gli indirizzi.")],
    )
    r2 = client.chat(model, appended, 8192, num_predict=120)
    modified = build_messages(project, "header", filler_tokens=4000, system_nonce="[run changed]\n")
    r3 = client.chat(model, modified, 8192, num_predict=120)
    out["prefix_reuse_8k"] = {
        "first": strip_text(r1),
        "append_only": strip_text(r2),
        "modified_prefix": strip_text(r3),
    }

    r = client.chat(model, build_messages(opening, "header"), 16384, num_predict=8)
    out["reload_16k"] = strip_text(r)
    out["ps_16k"] = client.ps()
    msgs = build_messages(project, "header", filler_tokens=8000, system_nonce=f"[run {uuid.uuid4()}]\n")
    out["fresh_16k"] = {"target_tokens": 8000, **strip_text(client.chat(model, msgs, 16384, num_predict=120))}

    r = client.chat(model, build_messages(opening, "header"), 8192, num_predict=8)
    out["reload_back_8k"] = strip_text(r)

    RESULTS.mkdir(parents=True, exist_ok=True)
    path = RESULTS / f"latency_{target}_{safe(model)}.json"
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return out


# --------------------------------------------------------------------------- moves


def first_sentence(utterance: str) -> bool:
    return len(utterance) >= 10 and bool(SENTENCE_END.search(utterance))


def header_marker(text: str, now: float, marks: dict[str, float]) -> None:
    if "first_sentence_s" in marks or "\n" not in text:
        return
    if first_sentence(text.partition("\n")[2].strip()):
        marks["first_sentence_s"] = now


def json_marker(text: str, now: float, marks: dict[str, float]) -> None:
    if "first_sentence_s" in marks:
        return
    try:
        partial = from_json(text, allow_partial="trailing-strings")
    except ValueError:
        return
    if isinstance(partial, dict) and first_sentence(str(partial.get("utterance", "")).strip()):
        marks["first_sentence_s"] = now


def analyse(fmt: str, text: str) -> dict[str, Any]:
    info: dict[str, Any] = {"valid": False}
    if fmt == "header":
        header, _, utterance = text.strip().partition("\n")
        m = HEADER_RE.match(header.strip())
        info.update(valid=bool(m and utterance.strip()), action=m.group(1) if m else None,
                    topic=m.group(2) if m else None)
    else:
        try:
            data = json.loads(text)
            utterance = str(data.get("utterance", ""))
            info.update(valid=data.get("action") in ACTIONS and bool(utterance.strip()),
                        action=data.get("action"), topic=data.get("topic_id"), key_order=list(data))
        except (json.JSONDecodeError, AttributeError):
            utterance = ""
    utterance = utterance.strip()
    words = re.findall(r"[\wàèéìòù']+", utterance.lower())
    info.update(
        utterance=utterance,
        words=len(words),
        questions=utterance.count("?"),
        italian_ratio=round(sum(w in ITALIAN_WORDS for w in words) / max(len(words), 1), 2),
    )
    return info


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    values = sorted(values)
    k = min(len(values) - 1, max(0, round(q * (len(values) - 1))))
    return round(values[k], 3)


def run_moves(target: str, model: str, n: int) -> dict[str, Any]:
    client = Ollama(BASES[target])
    free_gpu(target, client)
    client.chat(model, build_messages(SCENARIO["states"][0], "header"), 8192, num_predict=4)  # warm up
    states = SCENARIO["states"]
    RESULTS.mkdir(parents=True, exist_ok=True)
    raw_path = RESULTS / f"moves_{target}_{safe(model)}.jsonl"
    summary: dict[str, Any] = {"target": target, "model": model, "n_per_format": n}
    with raw_path.open("w", encoding="utf-8") as raw:
        for fmt in ("header", "json"):
            rows = []
            for i in range(n):
                state = states[i % len(states)]
                r = client.chat(
                    model,
                    build_messages(state, fmt),
                    8192,
                    schema=MOVE_SCHEMA if fmt == "json" else None,
                    num_predict=220,
                    on_text=header_marker if fmt == "header" else json_marker,
                )
                row = {"fmt": fmt, "i": i, "state": state["name"], **strip_text(r), **analyse(fmt, r["text"])}
                row["raw"] = r["text"]
                rows.append(row)
                raw.write(json.dumps(row, ensure_ascii=False) + "\n")
                raw.flush()
            fs = [r["first_sentence_s"] for r in rows if r.get("first_sentence_s")]
            summary[fmt] = {
                "valid_rate": round(sum(r["valid"] for r in rows) / len(rows), 3),
                "first_sentence_p50_s": percentile(fs, 0.5),
                "first_sentence_p95_s": percentile(fs, 0.95),
                "ttft_p50_s": percentile([r["ttft_s"] for r in rows if r["ttft_s"]], 0.5),
                "one_question_rate": round(sum(r["questions"] == 1 for r in rows) / len(rows), 3),
                "under_60_words_rate": round(sum(r["words"] <= 60 for r in rows) / len(rows), 3),
                "italian_rate": round(sum(r["italian_ratio"] >= 0.15 for r in rows) / len(rows), 3),
                "gen_tps_p50": percentile([r["gen_tps"] for r in rows if r.get("gen_tps")], 0.5),
            }
            if fmt == "json":
                orders = [tuple(r.get("key_order") or ()) for r in rows]
                summary[fmt]["key_orders"] = {",".join(k): orders.count(k) for k in set(orders)}
            if fmt == "header":
                write_quality_review(target, model, rows[: len(states)])
    (RESULTS / f"moves_{target}_{safe(model)}_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return summary


def write_quality_review(target: str, model: str, rows: list[dict[str, Any]]) -> None:
    by_name = {s["name"]: s for s in SCENARIO["states"]}
    lines = [f"# Interviewer moves for manual review: {model} ({target})", ""]
    for row in rows:
        state = by_name[row["state"]]
        lines += [
            f"## {row['state']}",
            "",
            f"- Candidate answer: {state['answer'] or '(opening)'}",
            f"- Directive: {state['directive']}",
            f"- Header valid: {row['valid']} · action: {row.get('action')} · topic: {row.get('topic')}"
            f" · words: {row['words']} · questions: {row['questions']}",
            "",
            "```",
            row["raw"].strip(),
            "```",
            "",
        ]
    (RESULTS / f"quality_{target}_{safe(model)}.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("latency", "moves"):
        p = sub.add_parser(name)
        p.add_argument("--target", choices=sorted(BASES), default="container")
        p.add_argument("--model", required=True)
        if name == "moves":
            p.add_argument("--n", type=int, default=50)
    args = parser.parse_args()
    if args.cmd == "latency":
        run_latency(args.target, args.model)
    else:
        run_moves(args.target, args.model, args.n)


if __name__ == "__main__":
    main()
