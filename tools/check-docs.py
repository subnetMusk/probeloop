"""Check local Markdown links and anchors in repository documentation without network requests."""

import re
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]


def slug(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text).replace("`", "").lower()
    return re.sub(r"[^\w\- ]", "", text).replace(" ", "-")


def anchors(path: Path) -> set[str]:
    result = set()
    counts = {}
    body = re.sub(r"```.*?```", "", path.read_text("utf-8"), flags=re.S)
    for match in re.finditer(r"^#{1,6}\s+(.+)$", body, re.M):
        value = slug(match[1].strip())
        count = counts.get(value, 0)
        counts[value] = count + 1
        result.add(value if not count else f"{value}-{count}")
    return result


def main() -> None:
    documents = [*ROOT.glob("*.md"), *ROOT.joinpath("docs").rglob("*.md"), *ROOT.joinpath("spikes").glob("*.md")]
    failures = []
    for path in documents:
        body = re.sub(r"```.*?```", "", path.read_text("utf-8"), flags=re.S)
        for match in re.finditer(r"\[[^\]\n]+\]\(([^\s)]+)\)", body):
            url = match[1].strip("<>")
            if "://" in url or url.startswith("mailto:"):
                continue
            relative, _, anchor = unquote(url).partition("#")
            target = (path.parent / relative).resolve() if relative else path
            if not target.exists():
                failures.append(f"{path.relative_to(ROOT)}: missing {url}")
            elif anchor and target.suffix == ".md" and anchor not in anchors(target):
                failures.append(f"{path.relative_to(ROOT)}: missing anchor {url}")
    if failures:
        raise SystemExit("\n".join(failures))
    print(f"Checked local links and anchors in {len(documents)} documents.")


if __name__ == "__main__":
    main()
