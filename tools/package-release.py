"""Package only the supported runtime and OS launchers, with immutable image digests."""

import argparse
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

import yaml

ROOT = Path(__file__).resolve().parents[1]


def package(version: str, digests: dict[str, str], output: Path) -> None:
    configuration = yaml.safe_load((ROOT / "compose.yaml").read_text())
    names = ("backend", "stt-worker", "tts-piper", "provisioner")
    configuration["services"] = {
        name: configuration["services"][name] for name in names
    }
    configuration["volumes"] = {
        name: value for name, value in configuration["volumes"].items() if name in ("data", "models")
    }
    for name, service in configuration["services"].items():
        image = "backend" if name == "provisioner" else name
        digest = digests[image]
        if not digest.startswith("sha256:") or len(digest) != 71:
            raise ValueError("expected a multi-platform image digest for each runtime image")
        service.pop("build", None)
        service["image"] = f"ghcr.io/subnetmusk/probeloop-{image}@{digest}"
    configuration["services"]["backend"]["ports"] = ["127.0.0.1:${PROBELOOP_PORT:-8000}:8000"]
    configuration["services"]["backend"]["environment"]["PROBELOOP_ALLOWED_ORIGINS"] = (
        '["http://127.0.0.1:${PROBELOOP_PORT:-8000}","http://localhost:${PROBELOOP_PORT:-8000}"]'
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        def write(name: str, content: str, executable: bool = False) -> None:
            entry = ZipInfo(f"ProbeLoop-{version}/{name}")
            entry.external_attr = (0o100755 if executable else 0o100644) << 16
            entry.compress_type = ZIP_DEFLATED
            archive.writestr(entry, content.replace("\r\n", "\n"))

        write("compose.yaml", yaml.safe_dump(configuration, sort_keys=False))
        for name in ("Start.cmd", "Start.ps1", "Start.sh", "README.txt"):
            write(name, (ROOT / "installer" / name).read_text(), name.endswith(".sh"))
        write("Start.command", (ROOT / "installer/Start.sh").read_text(), True)
        write("images.json", json.dumps({"version": version, "digests": digests}, indent=2))
        for name in ("LICENSE", "NOTICE", "THIRD_PARTY_NOTICES.md"):
            write(name, (ROOT / name).read_text())
        for notice in sorted((ROOT / "licenses").glob("*.txt")):
            write(f"licenses/{notice.name}", notice.read_text())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--digests", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    package(args.version, json.loads(args.digests.read_text()), args.output)
