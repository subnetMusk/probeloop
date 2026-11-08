"""A minimal PDF writer for synthetic test documents (text lines, colours, filled boxes).

It writes just enough of the format for real PDF parsers: one Helvetica font with WinAnsi
encoding, A4 pages, and a cross-reference table.
"""

from __future__ import annotations

from dataclasses import dataclass

PAGE_W, PAGE_H = 595, 842


@dataclass(frozen=True, slots=True)
class Text:
    x: float
    y: float
    text: str
    size: float = 11
    rgb: tuple[float, float, float] = (0, 0, 0)


@dataclass(frozen=True, slots=True)
class Box:
    x: float
    y: float
    w: float
    h: float
    rgb: tuple[float, float, float]


def _escape(text: str) -> bytes:
    raw = text.encode("cp1252", errors="replace")
    return raw.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def _content(items: list[Text | Box]) -> bytes:
    out = []
    for item in items:
        r, g, b = item.rgb
        if isinstance(item, Box):
            out.append(f"{r} {g} {b} rg {item.x} {item.y} {item.w} {item.h} re f".encode())
        else:
            out.append(
                f"{r} {g} {b} rg BT /F1 {item.size} Tf {item.x} {item.y} Td (".encode()
                + _escape(item.text)
                + b") Tj ET"
            )
    return b"\n".join(out)


def write_pdf(pages: list[list[Text | Box]]) -> bytes:
    objects: list[bytes] = []
    font_id = 3 + 2 * len(pages)
    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(len(pages)))
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode())
    for i, items in enumerate(pages):
        content = _content(items)
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_W} {PAGE_H}] "
            f"/Contents {4 + 2 * i} 0 R /Resources << /Font << /F1 {font_id} 0 R >> >> >>".encode()
        )
        objects.append(
            f"<< /Length {len(content)} >>\nstream\n".encode() + content + b"\nendstream"
        )
    objects.append(
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"
    )
    body = b"%PDF-1.4\n"
    offsets = []
    for number, obj in enumerate(objects, start=1):
        offsets.append(len(body))
        body += f"{number} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(body)
    body += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    body += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    body += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return body


def text_pdf(lines: list[str], *, size: float = 11, per_page: int = 60) -> bytes:
    """Plain lines of text, top to bottom, on as many pages as needed."""
    pages: list[list[Text | Box]] = []
    for start in range(0, max(len(lines), 1), per_page):
        chunk = lines[start : start + per_page]
        pages.append(
            [Text(50, PAGE_H - 60 - n * (size + 2), line, size) for n, line in enumerate(chunk)]
        )
    return write_pdf(pages)
