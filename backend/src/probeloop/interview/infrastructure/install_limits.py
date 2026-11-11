"""Install the approved ONNX classifier from a local export or an HTTPS directory."""

from __future__ import annotations

import argparse
import shutil
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from probeloop.interview.infrastructure.onnx_limits import model_spec, verify_model


def install(destination: Path, *, source: Path | None = None, url: str | None = None) -> None:
    if (source is None) == (url is None):
        raise ValueError("choose a local source or an HTTPS model URL")
    if url and urlsplit(url).scheme != "https":
        raise ValueError("the model URL must use HTTPS")
    spec = model_spec()
    if destination.exists():
        verify_model(destination, spec)
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".limits-", dir=destination.parent) as temporary:
        staging = Path(temporary) / "model"
        staging.mkdir()
        for name in spec.files:
            target = staging / name
            target.parent.mkdir(parents=True, exist_ok=True)
            if source is not None:
                if (source / name).stat().st_size != spec.sizes[name]:
                    raise ValueError("stated-limit model checksum or size mismatch")
                shutil.copyfile(source / name, target)
            else:
                assert url is not None
                with httpx.stream(
                    "GET", f"{url.rstrip('/')}/{name}", follow_redirects=True, timeout=120
                ) as response:
                    response.raise_for_status()
                    received = 0
                    with target.open("wb") as stream:
                        for chunk in response.iter_bytes():
                            received += len(chunk)
                            if received > spec.sizes[name]:
                                raise ValueError("stated-limit download exceeds the expected size")
                            stream.write(chunk)
        verify_model(staging, spec)
        staging.rename(destination)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--source", type=Path)
    source.add_argument("--url")
    parser.add_argument("--destination", type=Path, default=Path("/models/stated-limits/v1"))
    args = parser.parse_args()
    install(args.destination, source=args.source, url=args.url)
    print("Stated-limit model installed and checksums verified.")


if __name__ == "__main__":
    main()
