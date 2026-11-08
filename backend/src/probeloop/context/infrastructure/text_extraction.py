"""Text extraction from uploaded files: plain text, Markdown, JSON, XML, HTML, DOCX and PDF.

Files come from the user but are still untrusted input: parsing runs in a separate process with
a time limit, and PDFs are limited in pages. PDF text that a reader would not see (white or
near-invisible characters, tiny fonts) is reported as a warning, because it is the usual way to
hide instructions for a model in a CV.

HTML and XML are reduced to their text with the standard library's tolerant HTML parser: scripts
and styles are dropped, and no entity or external reference is ever resolved.
"""

from __future__ import annotations

import asyncio
import io
import json
import multiprocessing
import re
from concurrent.futures import ProcessPoolExecutor
from html.parser import HTMLParser
from pathlib import PurePath

from probeloop.context.application.ports import ExtractedText, ExtractionError

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_PDF_PAGES = 40
TIMEOUT_S = 30.0

MEDIA_TYPES = {
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".json": "application/json",
    ".xml": "application/xml",
    ".html": "text/html",
    ".htm": "text/html",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pdf": "application/pdf",
}


def media_type_of(filename: str) -> str:
    suffix = PurePath(filename).suffix.lower()
    media_type = MEDIA_TYPES.get(suffix)
    if media_type is None:
        supported = ", ".join(sorted({s.lstrip(".") for s in MEDIA_TYPES}))
        raise ExtractionError(f"unsupported file type '{suffix or filename}'; use {supported}")
    return media_type


class TextExtractor:
    """Runs the parsers in a worker process, so a hostile file cannot stall the server."""

    def __init__(self, *, timeout_s: float = TIMEOUT_S) -> None:
        self._timeout_s = timeout_s
        self._pool: ProcessPoolExecutor | None = None

    async def extract(self, data: bytes, filename: str) -> ExtractedText:
        if len(data) > MAX_FILE_BYTES:
            raise ExtractionError(f"the file is larger than {MAX_FILE_BYTES // (1024 * 1024)} MB")
        media_type = media_type_of(filename)
        if self._pool is None:
            self._pool = ProcessPoolExecutor(
                max_workers=1, mp_context=multiprocessing.get_context("spawn")
            )
        loop = asyncio.get_running_loop()
        future = loop.run_in_executor(self._pool, extract_sync, data, media_type)
        try:
            return await asyncio.wait_for(future, self._timeout_s)
        except TimeoutError as exc:
            self._restart()
            raise ExtractionError("the file took too long to read") from exc

    def close(self) -> None:
        if self._pool is not None:
            self._pool.shutdown(cancel_futures=True)
            self._pool = None

    def _restart(self) -> None:
        pool, self._pool = self._pool, None
        if pool is not None:
            for process in list(getattr(pool, "_processes", {}).values()):
                process.kill()  # a parser stuck on a hostile file does not stop by itself
            pool.shutdown(wait=False, cancel_futures=True)


def extract_sync(data: bytes, media_type: str) -> ExtractedText:
    """Parse one file. Runs in the worker process."""
    warnings: list[str] = []
    try:
        if media_type == "application/pdf":
            text, warnings = _pdf(data)
        elif media_type.endswith("wordprocessingml.document"):
            text = _docx(data)
        elif media_type in ("text/html", "application/xml"):
            text = _markup(_decode(data))
        elif media_type == "application/json":
            text = _json(_decode(data))
        else:
            text = _decode(data)
    except ExtractionError:
        raise
    except Exception as exc:
        raise ExtractionError(f"the file could not be read ({type(exc).__name__})") from exc
    text = normalise(text)
    if not text:
        raise ExtractionError("no text found in the file (scanned documents are not supported)")
    return ExtractedText(text=text, media_type=media_type, warnings=tuple(warnings))


def normalise(text: str) -> str:
    """Unix newlines, no trailing spaces, at most one empty line in a row."""
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    lines = [line.rstrip() for line in text.split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def _decode(data: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1")


def _json(text: str) -> str:
    try:
        return json.dumps(json.loads(text), ensure_ascii=False, indent=2)
    except json.JSONDecodeError as exc:
        raise ExtractionError("the JSON file is not valid") from exc


class _TextOnly(HTMLParser):
    SKIP = frozenset({"script", "style", "noscript", "template", "head"})
    BLOCK = frozenset(
        {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article"}
    )

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skipping = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.SKIP:
            self._skipping += 1
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP and self._skipping:
            self._skipping -= 1
        elif tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skipping:
            self.parts.append(data)


def _markup(text: str) -> str:
    parser = _TextOnly()
    parser.feed(text)
    parser.close()
    lines = (" ".join(line.split()) for line in "".join(parser.parts).split("\n"))
    return "\n".join(lines)


def _docx(data: bytes) -> str:
    from docx import Document  # imported in the worker process only

    document = Document(io.BytesIO(data))
    parts = [p.text for p in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            parts.append(" | ".join(cell.text.strip() for cell in row.cells))
    return "\n".join(parts)


def _pdf(data: bytes) -> tuple[str, list[str]]:
    import pdfplumber  # imported in the worker process only

    pages: list[str] = []
    hidden = 0
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        if len(pdf.pages) > MAX_PDF_PAGES:
            raise ExtractionError(f"the PDF has more than {MAX_PDF_PAGES} pages")
        for page in pdf.pages:
            fills = [
                r
                for r in page.rects
                if r.get("fill") and not _is_white(r.get("non_stroking_color"))
            ]

            def shown(obj: dict[str, object], fills: list[dict[str, object]] = fills) -> bool:
                return obj.get("object_type") != "char" or _visible(obj, fills)

            visible = page.filter(shown)
            hidden += sum(
                1 for c in page.chars if not str(c.get("text", "")).isspace() and not shown(c)
            )
            pages.append(visible.extract_text() or "")
    warnings = []
    if hidden:
        warnings.append(
            f"{hidden} characters of hidden text (white or tiny) were found and left out"
        )
    return "\n\n".join(pages), warnings


def _visible(char: dict[str, object], fills: list[dict[str, object]]) -> bool:
    """Whether a reader sees the character: not tiny, and not white on a white page. White text
    on a coloured box (a CV's dark sidebar) is visible."""
    size = char.get("size")
    if isinstance(size, int | float) and size < 2:
        return False
    if not _is_white(char.get("non_stroking_color")):
        return True
    return any(_inside(char, fill) for fill in fills)


def _inside(char: dict[str, object], box: dict[str, object]) -> bool:
    try:
        x = (float(char["x0"]) + float(char["x1"])) / 2  # type: ignore[arg-type]
        y = (float(char["top"]) + float(char["bottom"])) / 2  # type: ignore[arg-type]
        return (
            float(box["x0"]) <= x <= float(box["x1"])  # type: ignore[arg-type]
            and float(box["top"]) <= y <= float(box["bottom"])  # type: ignore[arg-type]
        )
    except (KeyError, TypeError, ValueError):
        return False


def _is_white(color: object) -> bool:
    if not isinstance(color, list | tuple) or not color:
        return False
    values = [float(v) for v in color if isinstance(v, int | float)]
    if len(values) == 1:  # grey
        return values[0] >= 0.95
    if len(values) == 3:  # RGB
        return min(values) >= 0.95
    if len(values) == 4:  # CMYK
        return max(values) <= 0.05
    return False
