"""Convert the final, locally trained state dict to Safetensors and verify every tensor.

Maintainer tool only. Run in a disposable CPU PyTorch container; torch is not a runtime dependency.
The original checkpoint is read with weights_only=True and is never modified.
"""

import argparse
import hashlib
import json
from pathlib import Path

import torch
from safetensors import safe_open
from safetensors.torch import save_file


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    torch.set_num_threads(2)
    state = torch.load(args.checkpoint, map_location="cpu", weights_only=True, mmap=True)
    if not isinstance(state, dict) or not {"head.weight", "head.bias"} <= state.keys():
        raise ValueError("expected the trained encoder and stated-limit classification head")
    if tuple(state["head.weight"].shape) != (2, 768):
        raise ValueError("unexpected stated-limit head shape")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if not args.output.exists():
        save_file(
            {key: value.contiguous() for key, value in state.items()},
            str(args.output),
            metadata={"format": "pt", "task": "stated-limit-classification", "status": "provisional"},
        )
    with safe_open(args.output, framework="pt", device="cpu") as exported:
        if set(exported.keys()) != state.keys():
            raise ValueError("Safetensors key mismatch")
        for name, expected in state.items():
            if not torch.equal(expected, exported.get_tensor(name)):
                raise ValueError(f"Safetensors tensor mismatch: {name}")
    print(json.dumps({
        "verified_tensors": len(state), "parameters": sum(t.numel() for t in state.values()),
        "checkpoint_sha256": digest(args.checkpoint), "safetensors_sha256": digest(args.output),
        "safetensors_bytes": args.output.stat().st_size,
    }))


if __name__ == "__main__":
    main()
