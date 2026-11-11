"""Rebuild the approved asset manifest from pinned upstream revisions (no weight downloads)."""

import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
SPECS = [
    (
        "parakeet", "Live speech recognition", "CC-BY-4.0",
        "istupakov/parakeet-tdt-0.6b-v3-onnx", "8f23f0c03c8761650bdb5b40aaf3e40d2c15f1ce",
        ["config.json", "encoder-model.int8.onnx", "decoder_joint-model.int8.onnx", "vocab.txt"],
    ),
    (
        "whisper", "Second transcription (optional)", "MIT",
        "mobiuslabsgmbh/faster-whisper-large-v3-turbo", "0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf",
        ["config.json", "model.bin", "preprocessor_config.json", "tokenizer.json", "vocabulary.json"],
    ),
    (
        "piper-it", "Italian voice · Serena", "CC-BY-4.0",
        "rhasspy/piper-voices", "cf910fb59f1d79ab3b625a63993a108751c6c25d",
        ["it/it_IT/serena/medium/" + name for name in
         ["it_IT-serena-medium.onnx", "it_IT-serena-medium.onnx.json", "MODEL_CARD"]],
    ),
]


def main() -> None:
    models = []
    for identity, title, license_id, repo, revision, names in SPECS:
        with urlopen(f"https://huggingface.co/api/models/{repo}/revision/{revision}?blobs=true") as r:
            metadata = json.load(r)
        entries = {entry["rfilename"]: entry for entry in metadata["siblings"]}
        assets = []
        for name in names:
            entry = entries[name]
            url = f"https://huggingface.co/{repo}/resolve/{revision}/{name}"
            digest = (entry.get("lfs") or {}).get("sha256")
            if digest is None:
                assert entry["size"] < 20_000_000
                with urlopen(url) as r:
                    digest = hashlib.sha256(r.read(20_000_001)).hexdigest()
            relative = (
                f"piper/{Path(name).name}" if identity == "piper-it" else
                f"hf/hub/models--{repo.replace('/', '--')}/snapshots/{revision}/{name}"
            )
            if name.endswith("MODEL_CARD"):
                relative = f"piper/it_IT-serena-medium.MODEL_CARD"
            assets.append({"path": relative, "url": url, "size": entry["size"], "sha256": digest})
        models.append({
            "id": identity, "title": title, "license": license_id,
            "source": f"https://huggingface.co/{repo}/tree/{revision}", "files": assets,
            "reference": None if identity == "piper-it" else {
                "path": f"hf/hub/models--{repo.replace('/', '--')}/refs/main", "value": revision,
            },
        })
    laya = json.loads((ROOT / "backend/src/probeloop/interview/infrastructure/limits_model.json").read_text())
    models.append({
        "id": "laya", "title": "Stated limits · Laya", "license": "Apache-2.0",
        "source": "https://huggingface.co/submsk/probeloop-laya-stated-limits", "reference": None,
        "files": [{"path": f"stated-limits/v1/{name}", "url": "", "size": laya["sizes"][name],
                   "sha256": digest} for name, digest in laya["files"].items()],
    })
    target = ROOT / "backend/src/probeloop/workspace/infrastructure/model_catalog.json"
    target.write_text(json.dumps({"version": 1, "models": models}, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
