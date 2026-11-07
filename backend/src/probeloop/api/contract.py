"""Writes the API contract the frontend's TypeScript types are generated from.

    python -m probeloop.api.contract ../frontend/src/api/contract

- `openapi.json`: the REST API;
- `ws-client.schema.json`: the messages the client sends on the session WebSocket;
- `ws-server.schema.json`: the messages the server sends on it.

CI regenerates these files and fails if they differ from the committed ones.
"""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from probeloop.api.app import create_app
from probeloop.api.schemas import IncomingMessage, OutgoingMessage
from probeloop.bootstrap import build
from probeloop.settings import Settings


def contract() -> dict[str, dict[str, Any]]:
    with tempfile.TemporaryDirectory() as data_dir:
        settings = Settings(data_dir=Path(data_dir), stt_url=None, tts_url=None)
        openapi = create_app(build(settings)).openapi()
    client = TypeAdapter(IncomingMessage).json_schema(mode="validation")
    server = TypeAdapter(OutgoingMessage).json_schema(mode="serialization")
    return {
        "openapi.json": openapi,
        "ws-client.schema.json": {"title": "ClientMessage", **client},
        "ws-server.schema.json": {"title": "ServerMessage", **server},
    }


def main() -> None:
    parser = argparse.ArgumentParser(prog="probeloop.api.contract")
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    args.directory.mkdir(parents=True, exist_ok=True)
    for name, document in contract().items():
        text = json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        (args.directory / name).write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
