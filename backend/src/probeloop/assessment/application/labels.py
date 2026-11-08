"""Presentation labels; criterion identifiers and rubric content remain language-independent."""

from __future__ import annotations

ITALIAN = {
    "Relevance to the target": "Pertinenza rispetto al ruolo",
    "Evidence of impact": "Evidenza dei risultati",
    "Specificity and ownership": "Specificità e contributo personale",
    "Clarity and structure": "Chiarezza e struttura",
    "Internal consistency": "Coerenza interna",
    "Depth for the target level": "Profondità rispetto al livello",
    "Machine readability": "Leggibilità automatica",
    "Motivation for the role": "Motivazione per il ruolo",
    "Relevant experience": "Esperienza pertinente",
    "Career narrative": "Percorso professionale",
    "Communication": "Comunicazione",
    "Ownership": "Contributo personale",
    "Specificity": "Specificità",
    "Results": "Risultati",
    "Reflection": "Riflessione",
    "Depth under follow-up": "Profondità negli approfondimenti",
    "Accuracy": "Correttezza",
    "Technical depth": "Profondità tecnica",
    "Problem solving": "Soluzione dei problemi",
    "Trade-offs": "Compromessi",
    "Practical experience": "Esperienza pratica",
    "Communication of reasoning": "Chiarezza del ragionamento",
    "Clarifying the situation": "Chiarimento della situazione",
    "Action plan": "Piano d'azione",
    "Reasoning": "Ragionamento",
    "Risks and trade-offs": "Rischi e compromessi",
    "Validation plan": "Piano di verifica",
    "strength": "Punto di forza",
    "improvement": "Da migliorare",
    "technical_error": "Verifica tecnica del modello",
    "question": "Domanda per esercitarti",
    "summary": "Sintesi",
    "rewrite": "Proposta di riscrittura",
    "hr": "Conoscitivo HR",
    "behavioral": "Comportamentale",
    "technical": "Tecnico",
    "hypothetical": "Ipotetico",
    "logistics": "Logistica e chiusura",
    "unclassified": "Non classificato",
    "answer_duration": "Durata della risposta",
    "speaking_rate": "Velocità del parlato",
    "fillers": "Intercalari",
    "long_pauses": "Pause lunghe",
    "pause_duration": "Durata delle pause",
    "answer_latency": "Latenza della risposta",
    "candidate_talk_share": "Quota di parola del candidato",
    "answer_budget_share": "Quota del tempo obiettivo usata per le risposte",
}


def label(value: str, language: str) -> str:
    return (
        ITALIAN.get(value, value.replace("_", " ")) if language == "it" else value.replace("_", " ")
    )
