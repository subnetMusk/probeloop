"""Verify the release archive uses fixed images, loopback ports and read-only model consumers."""

import importlib.util
import tempfile
from pathlib import Path
from zipfile import ZipFile

import yaml

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("package_release", ROOT / "tools/package-release.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
with tempfile.TemporaryDirectory() as directory:
    output = Path(directory) / "installer.zip"
    module.package("0.1.0-test", {name: "sha256:" + "a" * 64 for name in ("backend", "stt-worker", "tts-piper")}, output)
    with ZipFile(output) as archive:
        prefix = "ProbeLoop-0.1.0-test/"
        services = yaml.safe_load(archive.read(prefix + "compose.yaml"))["services"]
        assert set(services) == {"backend", "stt-worker", "tts-piper", "provisioner"}
        assert services["backend"]["ports"] == ["127.0.0.1:${PROBELOOP_PORT:-8000}:8000"]
        for name, service in services.items():
            assert "build" not in service
            assert "@sha256:" in service["image"]
            assert not service.get("ports") or name == "backend"
            assert not any("docker.sock" in mount for mount in service.get("volumes", []))
            assert f"models:/models{'' if name == 'provisioner' else ':ro'}" in service["volumes"]
        assert archive.getinfo(prefix + "Start.command").external_attr >> 16 & 0o111
        assert archive.getinfo(prefix + "Start.sh").external_attr >> 16 & 0o111
        assert not any(".env" in name or "model.safetensors" in name for name in archive.namelist())
print("Installer archive contracts passed.")
