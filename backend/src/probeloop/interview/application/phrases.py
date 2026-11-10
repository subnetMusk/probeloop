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

# Adaptive fallbacks. The candidate's answer is already recorded, so none of them asks for it
# again, and none speaks an objective title: titles are internal and written in English.
CONTINUE = {
    Language.ITALIAN: (
        "Grazie. C'è qualche altro aspetto di questo punto che ritiene importante aggiungere?"
    ),
    Language.ENGLISH: (
        "Thank you. Is there anything else on this point that you think is important to add?"
    ),
}

OPENING = {Language.ITALIAN: "Buongiorno.", Language.ENGLISH: "Hello."}

TOPIC_CHANGE = {
    Language.ITALIAN: "Passiamo a un altro aspetto.",
    Language.ENGLISH: "Let's move on to another area.",
}

# Keyed by language and by whether the objective asks for a real past example.
TOPIC_QUESTION = {
    (Language.ITALIAN, True): (
        "Mi descriva un'esperienza concreta rilevante per questo ruolo e il suo contributo "
        "personale; se non ne ha una, me lo dica pure."
    ),
    (Language.ITALIAN, False): (
        "Pensi a una situazione tipica di questo ruolo: come la affronterebbe e che cosa "
        "verificherebbe per primo?"
    ),
    (Language.ENGLISH, True): (
        "Please describe a concrete experience relevant to this role and your own "
        "contribution; if you have none, just say so."
    ),
    (Language.ENGLISH, False): (
        "Think of a typical situation in this role: how would you approach it, and what would "
        "you check first?"
    ),
}

CLOSING_QUESTION = {
    Language.ITALIAN: "Ha domande per noi?",
    Language.ENGLISH: "Do you have any questions for us?",
}

# Spoken after the candidate has answered the closing question, whatever the time left.
CLOSING_FAREWELL = {
    Language.ITALIAN: (
        "Ne prendo nota. La ringrazio per il colloquio e le auguro una buona giornata."
    ),
    Language.ENGLISH: "I have noted that. Thank you for the interview, and have a good day.",
}
