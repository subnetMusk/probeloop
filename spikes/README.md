# M1 technical spikes

This folder holds throwaway measurement scripts for milestone M1 (see
[docs/roadmap.md](../docs/roadmap.md)). It is not part of the application. The findings are
summarised in [docs/research/spike-results.md](../docs/research/spike-results.md).

`results/` and `audio/` are git-ignored, because they can contain voice recordings and
transcripts.

## Environment

```bash
docker compose -f spikes/compose.spike.yaml up -d ollama
docker compose -f spikes/compose.spike.yaml exec ollama ollama pull qwen3.5:9b
docker compose -f spikes/compose.spike.yaml --profile tts run --rm tts-piper \
  python -m piper.download_voices --data-dir /models/piper \
  it_IT-paola-medium it_IT-serena-medium it_IT-riccardo-x_low
docker compose -f spikes/compose.spike.yaml --profile tts up -d tts-piper
```

The volumes use the names planned for the main stack (`probeloop_ollama`, `probeloop_models`),
so models downloaded here are reused later.

## Runs

```bash
# LLM: latency, VRAM, prefix reuse, num_ctx reload; then interviewer move formats
docker compose -f spikes/compose.spike.yaml run --rm bench python llm_bench.py latency --target container --model qwen3.5:9b
docker compose -f spikes/compose.spike.yaml run --rm bench python llm_bench.py moves --target container --model qwen3.5:9b --n 50

# TTS: per-sentence latency, listening samples, synthetic STT material
docker compose -f spikes/compose.spike.yaml run --rm bench python tts_bench.py latency
docker compose -f spikes/compose.spike.yaml run --rm bench python tts_bench.py synthetic

# STT on CPU, with the LLM loaded on the GPU; BENCH_CPUS sets the container CPU limit
BENCH_CPUS=8 docker compose -f spikes/compose.spike.yaml run --rm bench python stt_bench.py --engine fw-turbo --preload-llm qwen3.5:9b
```

`--target native` measures the Ollama installed on the host, reached through
`host.docker.internal`. Each run unloads models from the other Ollama first, so only one of them
holds VRAM.

## Test recordings

Put recordings in `spikes/audio/`. Any common format works (`.wav`, `.m4a`, `.webm`, ...).
For read passages, add a `.txt` file with the same name containing the exact text, so that WER can
be computed. The passages to read are in [inputs/recording_script_it.md](inputs/recording_script_it.md).
