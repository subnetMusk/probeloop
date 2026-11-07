"""Command line tools.

    probeloop chat --type technical --language it --minutes 15

runs a text interview against a running backend: type the answer and press Enter; `/pause`,
`/resume` and `/end` send the matching commands.

    probeloop import-sessions

moves the sessions written by the file-based store used before the database (M4) into the
database. Their audio stays where it is.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import urllib.request
import uuid
from typing import Any

from websockets.asyncio.client import ClientConnection, connect


def _create_session(base_url: str, args: argparse.Namespace) -> str:
    body = json.dumps(
        {
            "interview_type": args.type,
            "difficulty": args.difficulty,
            "language": args.language,
            "duration_minutes": args.minutes,
        }
    ).encode()
    request = urllib.request.Request(  # noqa: S310 - URL comes from the developer's command line
        f"{base_url}/api/sessions", data=body, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(request) as response:  # noqa: S310
        return str(json.load(response)["id"])


async def _send(ws: ClientConnection, message_type: str, **fields: Any) -> None:
    await ws.send(json.dumps({"type": message_type, "client_msg_id": uuid.uuid4().hex, **fields}))


async def _read_answer(ws: ClientConnection) -> None:
    line = (await asyncio.to_thread(sys.stdin.readline)).strip()
    if line in ("/pause", "/resume", "/end"):
        await _send(
            ws,
            {"/pause": "session.pause", "/resume": "session.resume", "/end": "session.end"}[line],
        )
        return
    await _send(ws, "turn.start")
    await _send(ws, "turn.end", text=line)


async def chat(args: argparse.Namespace) -> int:
    base_url = args.url.rstrip("/")
    session_id = _create_session(base_url, args)
    ws_url = base_url.replace("http", "ws", 1) + f"/ws/sessions/{session_id}"
    print(f"session {session_id}")
    async with connect(ws_url) as ws:
        await _send(ws, "session.join", last_seq=0)
        await _send(ws, "session.start")
        answering: asyncio.Task[None] | None = None
        async for raw in ws:
            message = json.loads(raw)
            kind = message["type"]
            if kind == "interviewer.text.delta":
                print(message["text"], end="", flush=True)
            elif kind == "interviewer.move.completed":
                print(f"\n   [{message['action']} {message['topic_id']}]")
            elif kind == "state.changed":
                phase = message["phase"]
                if phase == "interviewer_speaking":
                    await _send(ws, "playback.finished")
                elif phase == "awaiting_candidate" and (answering is None or answering.done()):
                    remaining = round(message["remaining_s"] / 60, 1)
                    print(f"you ({remaining} min left) > ", end="", flush=True)
                    answering = asyncio.create_task(_read_answer(ws))
            elif kind == "session.ended":
                print(f"\n-- session ended: {message['reason'] or message['failure']}")
                return 0
            elif kind == "error":
                print(f"\n!! {message['code']}: {message['message']}")
    return 1


def main() -> None:
    parser = argparse.ArgumentParser(prog="probeloop")
    sub = parser.add_subparsers(dest="command", required=True)
    chat_parser = sub.add_parser("chat", help="run a text interview against a running backend")
    chat_parser.add_argument("--url", default="http://127.0.0.1:8000")
    chat_parser.add_argument(
        "--type", default="technical", choices=["hr", "behavioral", "technical", "mixed"]
    )
    chat_parser.add_argument("--difficulty", default="medium", choices=["easy", "medium", "hard"])
    chat_parser.add_argument("--language", default="it", choices=["it", "en"])
    chat_parser.add_argument("--minutes", type=int, default=15)
    sub.add_parser("import-sessions", help="move sessions from the old file store to the database")
    args = parser.parse_args()
    if args.command == "import-sessions":
        sys.exit(asyncio.run(import_sessions()))
    sys.exit(asyncio.run(chat(args)))


async def import_sessions() -> int:
    # Imported here: the chat client does not need the database stack.
    from probeloop.settings import Settings
    from probeloop.storage.database import create_engine, migrate, sessionmaker
    from probeloop.storage.legacy_import import import_file_sessions
    from probeloop.storage.session_files import SessionFiles
    from probeloop.storage.sql_sessions import SqlSessionStore

    settings = Settings()
    engine = create_engine(settings.effective_database_url)
    try:
        await migrate(engine)
        root = settings.data_dir / "sessions"
        store = SqlSessionStore(sessionmaker(engine), SessionFiles(root))
        result = await import_file_sessions(root, store)
    finally:
        await engine.dispose()
    print(
        f"imported {len(result.imported)}, already present {len(result.skipped)}, "
        f"unreadable {len(result.failed)}"
    )
    for session_id in result.failed:
        print(f"  unreadable: {session_id}")
    return 1 if result.failed else 0


if __name__ == "__main__":
    main()
