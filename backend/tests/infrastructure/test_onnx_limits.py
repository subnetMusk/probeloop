"""The reader contract uses a synthetic tokenizer and inference session; weights stay outside CI."""

from __future__ import annotations

import asyncio
import hashlib
import threading
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from tokenizers import Tokenizer, models, pre_tokenizers

from probeloop.interview.application.ports import LimitReaderUnavailable
from probeloop.interview.infrastructure import install_limits, onnx_limits


@pytest.fixture
def classifier(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    directory = tmp_path / "synthetic-model"
    (directory / "tokenizer").mkdir(parents=True)
    tokenizer = Tokenizer(
        models.WordLevel({"[UNK]": 0, "recall": 1, "I": 2, "cannot": 3}, unk_token="[UNK]")
    )
    tokenizer.pre_tokenizer = pre_tokenizers.Whitespace()
    tokenizer.save(str(directory / "tokenizer/tokenizer.json"))
    (directory / "limits-int8.onnx").write_bytes(b"synthetic-placeholder")
    names = ("limits-int8.onnx", "tokenizer/tokenizer.json")
    spec = onnx_limits.ModelSpec(
        "synthetic-v1",
        0.5,
        192,
        300,
        {name: hashlib.sha256((directory / name).read_bytes()).hexdigest() for name in names},
        {name: (directory / name).stat().st_size for name in names},
    )
    monkeypatch.setattr(onnx_limits, "model_spec", lambda: spec)
    monkeypatch.setattr(install_limits, "model_spec", lambda: spec)
    sessions = []

    class Session:
        broken = False

        def __init__(self, path, options, providers):
            assert providers == ["CPUExecutionProvider"]
            sessions.append(self)

        def get_inputs(self):
            return [
                SimpleNamespace(name=name, type="tensor(int64)")
                for name in ("input_ids", "attention_mask")
            ]

        def run(self, outputs, feeds):
            ids, mask = feeds["input_ids"], feeds["attention_mask"]
            assert ids.dtype == mask.dtype == np.int64
            assert ids.shape == mask.shape
            return [
                np.asarray([[0, np.nan if self.broken else 8 if 1 in row else -8] for row in ids])
            ]

    monkeypatch.setattr(onnx_limits.ort, "InferenceSession", Session)
    return directory, sessions


async def wait_loaded(reader: onnx_limits.OnnxStatedLimitReader) -> None:
    if reader._task is not None:
        await asyncio.wait_for(asyncio.shield(reader._task), 5)


async def test_the_reader_returns_whole_verbatim_sentences_and_empty_answers(classifier) -> None:
    directory, _ = classifier
    reader = onnx_limits.OnnxStatedLimitReader(directory)
    reader.start()
    await wait_loaded(reader)
    try:
        assert reader.state == "ready"
        result = await reader.read(
            "Describe your work.", "I cannot recall the exact rates. I planned two waves."
        )
        assert result.quotes == ("I cannot recall the exact rates.",)
        assert result.source_ref.startswith("synthetic-v1@")
        assert (await reader.read("Question?", "")).quotes == ()
        assert (await reader.read("Question?", "I planned two waves.")).quotes == ()
    finally:
        await reader.close()
    assert reader.state == "closed"


async def test_missing_loading_and_invalid_models_are_unavailable(
    classifier, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory, _ = classifier
    reader = onnx_limits.OnnxStatedLimitReader(directory / "absent")
    reader.start()
    assert reader.state == "missing"
    with pytest.raises(LimitReaderUnavailable, match="Laya is unavailable"):
        await reader.check()

    reader = onnx_limits.OnnxStatedLimitReader(directory)
    entered, release = threading.Event(), threading.Event()
    load = reader._load_sync

    def delayed():
        entered.set()
        assert release.wait(5)
        return load()

    monkeypatch.setattr(reader, "_load_sync", delayed)
    reader.start()
    try:
        await asyncio.to_thread(entered.wait, 5)
        with pytest.raises(LimitReaderUnavailable):
            await reader.read("Question?", "I cannot recall the rates.")
    finally:
        release.set()
        await wait_loaded(reader)
        await reader.close()

    (directory / "limits-int8.onnx").write_bytes(b"corrupted")
    reader = onnx_limits.OnnxStatedLimitReader(directory)
    reader.start()
    await wait_loaded(reader)
    assert reader.state == "failed"
    with pytest.raises(LimitReaderUnavailable):
        await reader.read("Question?", "I cannot recall the rates.")
    await reader.close()


async def test_invalid_inference_scores_disable_the_classifier(classifier) -> None:
    directory, sessions = classifier
    reader = onnx_limits.OnnxStatedLimitReader(directory)
    reader.start()
    await wait_loaded(reader)
    sessions[0].broken = True
    with pytest.raises(LimitReaderUnavailable):
        await reader.read("Question?", "I cannot recall the rates.")
    assert reader.state == "failed"
    await reader.close()


def test_installation_checks_every_file_before_publishing_the_directory(
    classifier, tmp_path: Path
) -> None:
    source, _ = classifier
    destination = tmp_path / "installed"
    install_limits.install(destination, source=source)
    install_limits.install(destination, source=source)  # idempotent
    assert (destination / "limits-int8.onnx").read_bytes() == b"synthetic-placeholder"
    (source / "limits-int8.onnx").write_bytes(b"corrupted")
    with pytest.raises(ValueError, match="checksum"):
        install_limits.install(tmp_path / "rejected", source=source)
    assert not (tmp_path / "rejected").exists()


@pytest.mark.live
async def test_the_installed_model_reads_synthetic_italian_limits() -> None:
    directory = Path("/models/stated-limits/v1")
    if not await asyncio.to_thread(directory.is_dir):
        pytest.skip("install the stated-limit model first")
    reader = onnx_limits.OnnxStatedLimitReader(directory)
    reader.start()
    if reader._task is not None:
        await asyncio.wait_for(asyncio.shield(reader._task), 240)
    try:
        assert reader.state == "ready"
        question = "Quali valori hai misurato prima e dopo l'intervento?"
        answer = "Ho confrontato i dati. Non ricordo i valori esatti prima e dopo l'intervento."
        result = await reader.read(question, answer)
        assert "Non ricordo i valori esatti prima e dopo l'intervento." in result.quotes
        assert not (
            await reader.read(question, "Ho misurato 12 prima e 15 dopo l'intervento.")
        ).quotes
    finally:
        await reader.close()
