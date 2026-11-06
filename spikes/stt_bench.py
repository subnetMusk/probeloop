"""M1 spike: CPU speech recognition with simulated incremental transcription.

Throwaway code, not part of the application. Results are written to /results/stt/.

For every audio file the script measures a full pass and a simulated incremental pass: Silero VAD
cuts segments at pauses (or after 15 s), each segment is transcribed as soon as it "arrives" in
real time, and the tail latency is the time between the end of the audio (the end-of-answer
click) and the end of the last transcription. Reference transcripts (same stem, .txt) give WER.

Usage (inside the bench container):
    python stt_bench.py --engine fw-turbo [--preload-llm qwen3.5:9b]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import resource
import time
from pathlib import Path
from typing import Any, Callable

import httpx
import jiwer
import numpy as np
from faster_whisper import WhisperModel, decode_audio
from faster_whisper.vad import VadOptions, get_speech_timestamps

SR = 16000
CPUS = int(os.environ.get("BENCH_CPUS", "8"))
AUDIO_DIRS = [Path("/audio"), Path("/results/stt_synthetic")]
AUDIO_EXT = {".wav", ".m4a", ".mp3", ".ogg", ".webm", ".flac", ".aac", ".opus"}
VOCABULARY = (
    "FastAPI, PostgreSQL, Redis, Docker, pytest, OR-Tools, Kafka, Kubernetes, EXPLAIN ANALYZE, "
    "microservizio, cache, API, backend."
)
HALLUCINATION_BLOCKLIST = ("sottotitoli", "amara.org", "grazie per la visione", "iscriviti")
VAD_MAX_S = float(os.environ.get("VAD_MAX_S", "15"))
VAD = VadOptions(min_silence_duration_ms=600, max_speech_duration_s=VAD_MAX_S, speech_pad_ms=200)


def normalize(text: str) -> str:
    text = text.lower().replace("'", " ").replace("’", " ")
    text = re.sub(r"[^\w\s-]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


class Engine:
    name: str

    def transcribe(self, audio: np.ndarray, prompt: str | None) -> str:
        raise NotImplementedError

    def full_pass(self, audio: np.ndarray) -> str:
        return self.transcribe(audio, VOCABULARY)


class FasterWhisper(Engine):
    def __init__(self, model: str) -> None:
        self.name = f"faster-whisper-{model}-int8"
        self.model = WhisperModel(model, device="cpu", compute_type="int8", cpu_threads=CPUS)

    def transcribe(self, audio: np.ndarray, prompt: str | None, *, vad: bool = False) -> str:
        segments, _ = self.model.transcribe(
            audio,
            language="it",
            beam_size=1,
            condition_on_previous_text=False,
            initial_prompt=prompt,
            vad_filter=vad,
        )
        return " ".join(s.text.strip() for s in segments).strip()

    def full_pass(self, audio: np.ndarray) -> str:
        segments, _ = self.model.transcribe(
            audio, language="it", beam_size=1, condition_on_previous_text=False,
            initial_prompt=VOCABULARY, vad_filter=True,
        )
        return " ".join(s.text.strip() for s in segments).strip()


class Parakeet(Engine):
    def __init__(self) -> None:
        import onnx_asr
        import onnxruntime as ort

        self.name = "parakeet-tdt-0.6b-v3"
        options = ort.SessionOptions()
        options.intra_op_num_threads = CPUS
        try:
            self.model = onnx_asr.load_model("nemo-parakeet-tdt-0.6b-v3", quantization="int8",
                                             sess_options=options)
            self.name += "-int8"
        except Exception as exc:  # noqa: BLE001 - spike: fall back to the default weights
            print(f"int8 weights unavailable ({exc}); using default weights")
            self.model = onnx_asr.load_model("nemo-parakeet-tdt-0.6b-v3", sess_options=options)

    def transcribe(self, audio: np.ndarray, prompt: str | None) -> str:
        return str(self.model.recognize(audio, sample_rate=SR)).strip()

    def full_pass(self, audio: np.ndarray) -> str:
        # Parakeet accepts at most 20-30 s per call, so the full pass also goes through VAD segments.
        return " ".join(self.transcribe(audio[s["start"]:s["end"]], None) for s in speech_segments(audio))


def make_engine(name: str) -> Engine:
    factories: dict[str, Callable[[], Engine]] = {
        "fw-turbo": lambda: FasterWhisper("large-v3-turbo"),
        "fw-small": lambda: FasterWhisper("small"),
        "parakeet": Parakeet,
    }
    return factories[name]()


def speech_segments(audio: np.ndarray) -> list[dict[str, int]]:
    return get_speech_timestamps(audio, vad_options=VAD, sampling_rate=SR)


def timed(fn: Callable[[], str]) -> tuple[str, float]:
    t0 = time.perf_counter()
    text = fn()
    return text, time.perf_counter() - t0


def incremental(engine: Engine, audio: np.ndarray) -> dict[str, Any]:
    """Simulate segments arriving in real time and being transcribed one after another."""
    segments = speech_segments(audio)
    finish = 0.0
    committed: list[str] = []
    max_lag = 0.0
    for seg in segments:
        available_at = seg["end"] / SR
        start = max(available_at, finish)
        prompt = (" ".join(committed)[-200:] + " " + VOCABULARY).strip()
        text, elapsed = timed(lambda s=seg, p=prompt: engine.transcribe(audio[s["start"]:s["end"]], p))
        finish = start + elapsed
        max_lag = max(max_lag, finish - available_at)
        if text and not any(b in text.lower() for b in HALLUCINATION_BLOCKLIST):
            committed.append(text)
    audio_end = len(audio) / SR
    return {
        "segments": len(segments),
        "tail_s": round(max(0.0, finish - audio_end), 3),
        "max_lag_s": round(max_lag, 3),
        "text": " ".join(committed),
    }


def audio_files() -> list[Path]:
    files: list[Path] = []
    for d in AUDIO_DIRS:
        if d.exists():
            files += sorted(p for p in d.iterdir() if p.suffix.lower() in AUDIO_EXT)
    return files


def preload_llm(model: str) -> None:
    base = os.environ["OLLAMA_CONTAINER_URL"]
    httpx.post(f"{base}/api/generate", json={"model": model, "keep_alive": "30m",
                                             "options": {"num_ctx": 8192}}, timeout=600).raise_for_status()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine", choices=["fw-turbo", "fw-small", "parakeet"], required=True)
    parser.add_argument("--preload-llm")
    args = parser.parse_args()
    if args.preload_llm:
        preload_llm(args.preload_llm)

    t0 = time.perf_counter()
    engine = make_engine(args.engine)
    load_s = time.perf_counter() - t0
    engine.transcribe(np.zeros(SR, dtype=np.float32), None)  # warm up

    rows = []
    for path in audio_files():
        audio = decode_audio(str(path), sampling_rate=SR)
        seconds = len(audio) / SR
        full_text, full_s = timed(lambda a=audio: engine.full_pass(a))
        inc = incremental(engine, audio)
        row: dict[str, Any] = {
            "file": path.name,
            "source": path.parent.name,
            "audio_s": round(seconds, 1),
            "full_s": round(full_s, 2),
            "rtf_full": round(full_s / seconds, 3),
            **{k: v for k, v in inc.items() if k != "text"},
            "text_incremental": inc["text"],
            "text_full": full_text,
        }
        ref = path.with_suffix(".txt")
        if ref.exists():
            reference = normalize(ref.read_text(encoding="utf-8"))
            row["wer_incremental"] = round(jiwer.wer(reference, normalize(inc["text"]) or "-"), 3)
            row["wer_full"] = round(jiwer.wer(reference, normalize(full_text) or "-"), 3)
        rows.append(row)
        print(json.dumps({k: v for k, v in row.items() if not k.startswith("text")}))

    # Two minutes of near-silence (about -60 dBFS white noise).
    silence = np.random.default_rng(0).normal(0, 0.001, SR * 120).astype(np.float32)
    silence_result = {
        "incremental_text": incremental(engine, silence)["text"],
        "raw_no_vad_text": engine.transcribe(silence[: SR * 30], None),
    }

    tails = sorted(r["tail_s"] for r in rows)
    summary = {
        "engine": engine.name,
        "cpus": CPUS,
        "vad_max_s": VAD_MAX_S,
        "llm_preloaded": args.preload_llm,
        "model_load_s": round(load_s, 1),
        "max_rss_mb": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024),
        "files": len(rows),
        "rtf_full_mean": round(sum(r["rtf_full"] for r in rows) / max(len(rows), 1), 3),
        "tail_p50_s": tails[len(tails) // 2] if tails else None,
        "tail_max_s": tails[-1] if tails else None,
        "wer_incremental_mean": mean([r.get("wer_incremental") for r in rows]),
        "wer_full_mean": mean([r.get("wer_full") for r in rows]),
        "silence": silence_result,
    }
    out_dir = Path("/results/stt")
    out_dir.mkdir(parents=True, exist_ok=True)
    tag = f"{args.engine}_cpu{CPUS}_vad{VAD_MAX_S:g}{'_llm' if args.preload_llm else ''}"
    (out_dir / f"stt_{tag}.json").write_text(
        json.dumps({"summary": summary, "rows": rows}, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


def mean(values: list[float | None]) -> float | None:
    present = [v for v in values if v is not None]
    return round(sum(present) / len(present), 3) if present else None


if __name__ == "__main__":
    main()
