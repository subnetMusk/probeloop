from probeloop.context.domain.lines import logical_lines


def test_wrapped_bullets_and_broken_measures_become_one_line() -> None:
    text = (
        "E X P E R I E N C E\n"
        "\n"
        "Staff Nurse, Acute Medical Ward (32 beds)\n"
        "Northfield General Hospital (synthetic company), Leeds | 09/2023 - present\n"
        "- Care for up to eight acutely unwell patients per shift: observations, NEWS2, IV\n"
        "  therapy and medication rounds.\n"
        "- Introduced a handover sheet, which reduced handover time by 15\n"
        "% and was later adopted by two other wards.\n"
    )
    assert logical_lines(text) == [
        "E X P E R I E N C E",
        "Staff Nurse, Acute Medical Ward (32 beds)",
        "Northfield General Hospital (synthetic company), Leeds | 09/2023 - present",
        "- Care for up to eight acutely unwell patients per shift: observations, NEWS2, IV "
        "therapy and medication rounds.",
        "- Introduced a handover sheet, which reduced handover time by 15 % and was later "
        "adopted by two other wards.",
    ]


def test_paragraphs_join_while_headings_dates_and_sentences_start_lines() -> None:
    text = (
        "Profilo\n"
        "Backend developer con sei anni di esperienza su servizi Python per la logistica e\n"
        "l'e-commerce. Mi occupo di API e integrazione tra sistemi, basi dati relazionali e\n"
        "Kafka.\n"
        "Formazione\n"
        "March 2021 - present\n"
        "2018 Laurea triennale in Informatica, Universita' di Esempio. Tesi sulla schedulazione\n"
        "di veicoli con vincoli di finestra temporale.\n"
        "2023 - oggi   Assegnista di ricerca, Dipartimento di Scienze Statistiche\n"
        "              Progetto sulle stime per piccole aree.\n"
        "              Ho sviluppato in R il pacchetto del progetto.\n"
    )
    assert logical_lines(text) == [
        "Profilo",
        "Backend developer con sei anni di esperienza su servizi Python per la logistica e "
        "l'e-commerce. Mi occupo di API e integrazione tra sistemi, basi dati relazionali e "
        "Kafka.",
        "Formazione",
        "March 2021 - present",
        "2018 Laurea triennale in Informatica, Universita' di Esempio. Tesi sulla schedulazione "
        "di veicoli con vincoli di finestra temporale.",
        "2023 - oggi   Assegnista di ricerca, Dipartimento di Scienze Statistiche "
        "Progetto sulle stime per piccole aree.",
        "Ho sviluppato in R il pacchetto del progetto.",
    ]
