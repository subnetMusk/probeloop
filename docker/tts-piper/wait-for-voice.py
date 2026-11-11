"""Wait for the provisioner's verified voice, then exec unmodified Piper as its own program."""

import os
import sys
import time
from pathlib import Path

arguments = sys.argv[1:]
voice = arguments[arguments.index("-m") + 1] if "-m" in arguments else "it_IT-serena-medium"
model = Path("/models/piper") / f"{voice}.onnx"
while not (model.is_file() and Path(f"{model}.json").is_file()):
    print("Waiting for voice installation in ProbeLoop Settings.", flush=True)
    time.sleep(10)
os.execv(sys.executable, [sys.executable, "-m", "piper.http_server", "--host", "0.0.0.0",
                        "--port", "5000", "--data-dir", "/models/piper", *arguments])
