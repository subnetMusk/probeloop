"""Rebuild the synthetic PDF CV and DOCX offer used by the browser acceptance checks."""

from html import escape
from pathlib import Path

from docx import Document
from weasyprint import HTML

from probeloop.assessment.infrastructure.exports import BlockedFetcher

directory = Path(__file__).parent
source = directory.parents[3] / "evals/fixtures/synthetic/context"
cv = (source / "backend-it.txt").read_text()
HTML(
    string="<style>@page {size:A4;margin:20mm} body {font:11pt/1.5 sans-serif} "
    "pre {font:inherit;white-space:pre-wrap}</style><pre>" + escape(cv) + "</pre>",
    url_fetcher=BlockedFetcher(),
).write_pdf(directory / "synthetic-cv.pdf")
offer = Document()
for line in (source / "acceptance/offer-pagafacile-backend.txt").read_text().splitlines():
    offer.add_paragraph(line)
offer.save(str(directory / "synthetic-offer.docx"))
