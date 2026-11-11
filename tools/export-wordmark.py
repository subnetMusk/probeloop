"""Export the existing Space Grotesk wordmark as self-contained light/dark SVG paths."""

from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

ROOT = Path(__file__).resolve().parents[1]
FONT = ROOT / "frontend/node_modules/@fontsource-variable/space-grotesk/files/space-grotesk-latin-wght-normal.woff2"


def main() -> None:
    font = instantiateVariableFont(TTFont(FONT), {"wght": 700})
    glyphs = font.getGlyphSet()
    cmap = font.getBestCmap()
    paths = []
    position = 20
    for index, letter in enumerate("ProbeLoop"):
        name = cmap[ord(letter)]
        pen = SVGPathPen(glyphs)
        glyphs[name].draw(pen)
        paths.append((position, pen.getCommands(), index >= 5))
        position += font["hmtx"][name][0] - 25
    directory = ROOT / "docs/assets"
    directory.mkdir(exist_ok=True)
    for theme, foreground, accent in [("light", "#111827", "#7c3aed"), ("dark", "#f9fafb", "#a78bfa")]:
        content = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {position + 20} 1050" role="img" aria-labelledby="title"><title id="title">ProbeLoop</title>']
        content.append('<!-- Existing app wordmark; Space Grotesk Bold, SIL Open Font License 1.1. -->')
        for x, path, highlighted in paths:
            color = accent if highlighted else foreground
            content.append(f'<path fill="{color}" transform="translate({x} 820) scale(1 -1)" d="{path}"/>')
        content.append('</svg>')
        (directory / f"wordmark-{theme}.svg").write_text("\n".join(content) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
