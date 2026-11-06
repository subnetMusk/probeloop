"""M1 spike: Piper latency per sentence, listening samples, and synthetic STT test audio.

Throwaway code, not part of the application. Results are written to /results/tts/ and
/results/stt_synthetic/.

Usage (inside the bench container, with the tts-piper service running):
    python tts_bench.py latency
    python tts_bench.py synthetic
"""

from __future__ import annotations

import argparse
import io
import json
import os
import time
import wave
from pathlib import Path

import httpx

PIPER = os.environ["PIPER_URL"]
VOICES = ["it_IT-paola-medium", "it_IT-serena-medium", "it_IT-riccardo-x_low"]

# Sentences of about fifteen words, in the interviewer's register.
SENTENCES = [
    "Buongiorno Marco, grazie per essere qui oggi, iniziamo pure con una breve presentazione personale.",
    "Mi racconta quale problema concreto risolveva il microservizio di ottimizzazione dei percorsi che ha progettato?",
    "Quale parte del lavoro ha seguito personalmente e quali decisioni tecniche sono state prese da altri?",
    "Come avete misurato la riduzione dei tempi di pianificazione e su quanti giorni di dati reali?",
    "Parliamo di PostgreSQL: come capirebbe quale parte di una query lenta consuma più tempo?",
    "In quali casi un indice aggiuntivo può peggiorare le prestazioni di scrittura di una tabella?",
    "Mi descrive come organizza i test di integrazione quando il servizio dipende da un database?",
    "Le è capitato di non essere d'accordo con un collega su una scelta architetturale importante?",
    "Come ha sostenuto la sua posizione e che cosa ha deciso alla fine il resto del team?",
    "Abbiamo quasi finito il tempo a disposizione: ha qualche domanda da farmi su questa posizione?",
]

SAMPLE_PARAGRAPH = (
    "Buongiorno e benvenuto. Oggi parleremo della sua esperienza come sviluppatore backend, "
    "dei progetti che ha descritto nel curriculum e del suo modo di lavorare in gruppo. "
    "Per cominciare, mi racconta brevemente il suo percorso?"
)

# Candidate-style answers with technical vocabulary, used as synthetic STT test material.
PASSAGES = [
    "Negli ultimi tre anni ho lavorato come sviluppatore backend in un'agenzia di e-commerce. "
    "Il nostro stack era basato su Python e FastAPI, con PostgreSQL come database principale e Redis "
    "per la cache. Mi occupavo soprattutto delle API per la gestione degli ordini e dei pagamenti, "
    "e negli ultimi mesi ho seguito anche la migrazione dei servizi su Docker.",
    "Il microservizio di ottimizzazione dei percorsi riceveva ogni mattina gli ordini del giorno e "
    "calcolava i giri dei furgoni. Per il problema di routing usavamo OR-Tools, mentre le matrici delle "
    "distanze venivano salvate in Redis con una scadenza di un'ora. Grazie a questa cache il tempo medio "
    "di pianificazione è sceso da circa quaranta minuti a meno di cinque.",
    "Quando una query è lenta parto sempre da EXPLAIN ANALYZE, per vedere se il piano usa una scansione "
    "sequenziale e quanto tempo richiede ogni nodo. Poi valuto un indice mirato sulle colonne usate nei "
    "filtri, tenendo presente che ogni indice rallenta le scritture. A volte basta riscrivere la query "
    "o aggiungere una paginazione con chiave invece dell'offset.",
    "Organizzo i test su due livelli. I test unitari girano con pytest e usano dei fake per le dipendenze "
    "esterne, così sono veloci e deterministici. I test di integrazione invece avviano un vero PostgreSQL "
    "in un container durante la pipeline di integrazione continua. Ogni bug trovato in produzione "
    "diventa prima di tutto un test che fallisce.",
    "Una volta il team voleva introdurre Kafka per gestire gli eventi tra i servizi. Io ero contrario, "
    "perché il volume di messaggi non lo giustificava e avrebbe aumentato i costi operativi. Ho preparato "
    "una stima dei costi e un piccolo prototipo con una coda più semplice su Redis, e alla fine il team "
    "ha scelto quella soluzione, che funziona ancora oggi senza problemi.",
]


def synthesize(client: httpx.Client, text: str, voice: str) -> tuple[bytes, float]:
    t0 = time.perf_counter()
    r = client.post(f"{PIPER}/synthesize", json={"text": text, "voice": voice})
    r.raise_for_status()
    return r.content, time.perf_counter() - t0


def wav_seconds(data: bytes) -> float:
    with wave.open(io.BytesIO(data)) as w:
        return w.getnframes() / w.getframerate()


def run_latency() -> None:
    out_dir = Path("/results/tts")
    out_dir.mkdir(parents=True, exist_ok=True)
    results = {}
    with httpx.Client(timeout=120) as client:
        for voice in VOICES:
            synthesize(client, "Prova di caricamento della voce.", voice)  # load the voice once
            rows = []
            for sentence in SENTENCES:
                data, elapsed = synthesize(client, sentence, voice)
                seconds = wav_seconds(data)
                rows.append({"words": len(sentence.split()), "latency_s": round(elapsed, 3),
                             "audio_s": round(seconds, 2), "rtf": round(elapsed / seconds, 3)})
            sample, _ = synthesize(client, SAMPLE_PARAGRAPH, voice)
            (out_dir / f"sample_{voice}.wav").write_bytes(sample)
            latencies = sorted(r["latency_s"] for r in rows)
            results[voice] = {
                "latency_p50_s": latencies[len(latencies) // 2],
                "latency_max_s": latencies[-1],
                "rtf_mean": round(sum(r["rtf"] for r in rows) / len(rows), 3),
                "rows": rows,
            }
    (out_dir / "latency.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps({v: {k: r[k] for k in r if k != "rows"} for v, r in results.items()}, indent=2))


def run_synthetic() -> None:
    out_dir = Path("/results/stt_synthetic")
    out_dir.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=300) as client:
        for i, passage in enumerate(PASSAGES):
            voice = VOICES[i % 2]  # alternate paola and serena
            data, _ = synthesize(client, passage, voice)
            (out_dir / f"synth_{i:02d}.wav").write_bytes(data)
            (out_dir / f"synth_{i:02d}.txt").write_text(passage, encoding="utf-8")
            print(f"synth_{i:02d}.wav {wav_seconds(data):.1f}s ({voice})")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("cmd", choices=["latency", "synthetic"])
    args = parser.parse_args()
    run_latency() if args.cmd == "latency" else run_synthetic()


if __name__ == "__main__":
    main()
