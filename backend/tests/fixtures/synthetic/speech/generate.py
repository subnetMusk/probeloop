"""Regenerate the synthetic speech fixtures from a Piper HTTP server.

Each fixture is a sequence of sentences spoken by the Piper voice `it_IT-paola-medium` (CC0),
separated by silences of known length, with a faint noise floor (about -60 dBFS) so the silences
are not digital zero. The output is mono PCM16 at 16 kHz, the format of the capture path.
`manifest.json` records where each sentence starts and ends.

Requires numpy and a reachable Piper server, for example:

    docker run --rm --network <piper network> -v "$PWD:/out" -w /out python:3.13-slim \
        sh -c "pip install -q numpy==2.3.4 && python generate.py --piper-url http://tts-piper:5000"

Piper's synthesis is not deterministic, so regenerated files differ slightly; tests read the
manifest rather than hard-coded offsets.
"""

from __future__ import annotations

import argparse
import io
import json
import urllib.request
import wave
from pathlib import Path

import numpy as np

VOICE = "it_IT-paola-medium"
RATE = 16_000
NOISE_RMS = 0.001  # about -60 dBFS
TRIM_DBFS = -50.0  # leading and trailing samples below this are cut from each sentence

# name -> (leading silence, [(sentence, silence after it)])
FIXTURES: dict[str, tuple[float, list[tuple[str, float]]]] = {
    # Three answers separated by pauses well above the 600 ms that closes a segment.
    "three_sentences": (
        0.5,
        [
            ("Ho lavorato tre anni come sviluppatore backend.", 1.2),
            ("Usavamo soprattutto Python e PostgreSQL.", 1.2),
            ("Mi occupavo delle API per gli ordini.", 0.8),
        ],
    ),
    # Continuous speech with only short pauses: the 15 s cap must cut it at one of them.
    "long_answer": (
        0.3,
        [
            ("Il microservizio riceveva ogni mattina gli ordini del giorno.", 0.25),
            ("Poi calcolava i giri dei furgoni con un risolutore di vincoli.", 0.25),
            ("Le matrici delle distanze restavano in una cache per un'ora.", 0.25),
            ("Così il tempo di pianificazione scendeva da quaranta a cinque minuti.", 0.25),
            ("Il risultato veniva poi controllato da un operatore.", 0.25),
            ("Alla fine i percorsi venivano inviati agli autisti.", 0.8),
        ],
    ),
    # The candidate thinks for a while before answering.
    "late_start": (2.5, [("Sì, certo, posso fare un esempio concreto.", 1.0)]),
}


def synthesize(piper_url: str, text: str) -> tuple[np.ndarray, int]:
    body = json.dumps({"text": text, "voice": VOICE}).encode("utf-8")
    request = urllib.request.Request(
        f"{piper_url}/synthesize", data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        data = response.read()
    with wave.open(io.BytesIO(data)) as source:
        if source.getnchannels() != 1 or source.getsampwidth() != 2:
            raise ValueError("Piper returned audio that is not mono PCM16")
        rate = source.getframerate()
        pcm = np.frombuffer(source.readframes(source.getnframes()), dtype="<i2")
    return pcm.astype(np.float64) / 32768.0, rate


def trim(samples: np.ndarray, rate: int) -> np.ndarray:
    level = 10 ** (TRIM_DBFS / 20)
    loud = np.flatnonzero(np.abs(samples) > level)
    if loud.size == 0:
        raise ValueError("the synthesised sentence is silent")
    margin = int(0.02 * rate)
    return samples[max(loud[0] - margin, 0) : loud[-1] + margin]


def resample(samples: np.ndarray, rate: int) -> np.ndarray:
    """Windowed-sinc low-pass below the new Nyquist frequency, then linear interpolation."""
    if rate == RATE:
        return samples
    cutoff = 0.45 * RATE / rate  # as a fraction of the source sample rate
    taps = np.arange(-64, 65)
    kernel = 2 * cutoff * np.sinc(2 * cutoff * taps) * np.hamming(taps.size)
    filtered = np.convolve(samples, kernel / kernel.sum(), mode="same")
    positions = np.arange(0, samples.size * RATE // rate) * rate / RATE
    return np.interp(positions, np.arange(samples.size), filtered)


def build(
    piper_url: str, lead_s: float, sentences: list[tuple[str, float]]
) -> tuple[np.ndarray, list[dict[str, object]]]:
    parts = [np.zeros(round(lead_s * RATE))]
    offset = parts[0].size
    utterances: list[dict[str, object]] = []
    for text, pause_s in sentences:
        samples, rate = synthesize(piper_url, text)
        speech = resample(trim(samples, rate), rate)
        utterances.append(
            {
                "text": text,
                "start_s": round(offset / RATE, 3),
                "end_s": round((offset + speech.size) / RATE, 3),
            }
        )
        parts += [speech, np.zeros(round(pause_s * RATE))]
        offset += speech.size + parts[-1].size
    return np.concatenate(parts), utterances


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--piper-url", required=True)
    parser.add_argument("--out", type=Path, default=Path(__file__).parent)
    args = parser.parse_args()
    rng = np.random.default_rng(20261106)
    manifest: dict[str, object] = {"voice": VOICE, "sample_rate": RATE, "fixtures": {}}
    for name, (lead_s, sentences) in FIXTURES.items():
        audio, utterances = build(args.piper_url, lead_s, sentences)
        audio = np.clip(audio + rng.normal(0, NOISE_RMS, audio.size), -1.0, 1.0)
        pcm = (audio * 32767).astype("<i2").tobytes()
        with wave.open(str(args.out / f"{name}.wav"), "wb") as out:
            out.setnchannels(1)
            out.setsampwidth(2)
            out.setframerate(RATE)
            out.writeframes(pcm)
        manifest["fixtures"][name] = {  # type: ignore[index]
            "duration_s": round(audio.size / RATE, 3),
            "utterances": utterances,
        }
        print(f"{name}.wav {audio.size / RATE:.1f} s, {len(utterances)} sentences")
    (args.out / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
