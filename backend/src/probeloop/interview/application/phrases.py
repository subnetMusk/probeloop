"""Fixed interviewer phrases used when the LLM is not involved."""

from __future__ import annotations

from probeloop.interview.domain.model import Language

FALLBACK = {
    Language.ITALIAN: (
        "Mi scusi, ho avuto un piccolo problema tecnico. Può riprendere da dove si era interrotto?"
    ),
    Language.ENGLISH: (
        "Sorry, I had a small technical problem. Could you continue from where you stopped?"
    ),
}

FAREWELL = {
    Language.ITALIAN: (
        "Il tempo a nostra disposizione è terminato. La ringrazio per il colloquio e le auguro "
        "una buona giornata."
    ),
    Language.ENGLISH: (
        "We have run out of time. Thank you for the interview, and have a good day."
    ),
}
