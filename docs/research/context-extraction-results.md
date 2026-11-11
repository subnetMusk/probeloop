# M5 context extraction evaluation

> **Research and validation record.** Interpret measurements in their original conditions; they are not current runtime guarantees.
> Current operational guides: [documentation index](../README.md), [architecture](../architecture.md), and [status](../status.md).

Measured on 2026-11-08 using the native Ollama, `qwen3.5:9b` with an 8192-token context,
thinking off, extraction temperature 0.1 and `extract_facts.v1`. All evaluation code ran in the
rebuilt development container. Documents and labels are synthetic and kept in
`backend/evals/fixtures/synthetic/context/`.

Run with:

```bash
docker compose -f compose.yaml -f compose.dev.yaml run --rm --no-deps backend \
  python -m evals.context_extraction --output /tmp/context-eval.json
```

| CV | Language | Extracted facts | Verified quotes | Labelled facts recovered | Analysis time |
|---|---|---:|---:|---:|---:|
| Backend | Italian | 17 | 17 | 7/7 | 86.22 s |
| Frontend | Italian | 12 | 12 | 6/6 | 21.76 s |
| Data analyst | English | 7 | 7 | 6/6 | 10.83 s |
| IT support | English | 6 | 6 | 5/5 | 10.74 s |
| Logistics | Italian | 10 | 10 | 5/6 | 14.64 s |
| Total | | 52 | 52 | 29/30 | 144.19 s |

Verified-quote share is **100%**, above the predefined 90% threshold. Fact recall is **96.7%**:
an output must contain the label's identifying terms and a verified quote covering its source
span. The logistics role's dates were in the quote but omitted from the statement; this label
does not count as recovered. Evidence span coverage alone is 100%, and is a separate metric.
These deterministic checks are reproducible; they do not establish semantic entailment.

The hidden-text PDF fixture contains a visible synthetic CV line and a white-on-white instruction.
The parser warned about hidden text and excluded it. Unit tests also cover tiny text and visible
white text on a dark sidebar. HTML scripts/styles and XML external entities are excluded without
network access.

## Limits observed

- The backend CV produced long, repetitive quotes despite the prompt's request for short ones.
  Quote verification proves that the source text exists, not that every word of the statement is
  justified. One output called Redis a framework, an unsupported categorisation. Review remains
  necessary; the UI explains what the Declared badge means.
- The fixture set contains short, straightforward text CVs. It does not measure recall on complex
  PDF layouts, scanned CVs (unsupported), or long documents. No population-level accuracy claim
  follows from five synthetic documents.
- Times include area inference and model loading. The first run was slower; other container
  checks and image builds were running, so these are observed times, not an isolated benchmark.
- Requirement matching and area inference remain labelled model interpretations. Unknown fact
  references and unverified inferred evidence cannot establish a requirement match. Corrections
  withdraw affected matches, and the user must confirm the area before approval.
