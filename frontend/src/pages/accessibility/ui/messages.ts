import { defineMessages } from '@/shared/i18n'

export const accessibilityMessages = defineMessages({
  en: {
    title: 'Accessibility statement',
    updated: 'Self-assessment of 9 November 2026, not verified by a third party.',
    commitment: {
      title: 'Commitment',
      text: 'ProbeLoop aims to conform to the Web Content Accessibility Guidelines (WCAG) 2.2 at level AA.',
    },
    status: {
      title: 'Conformance status',
      text: 'Partially conformant: most of the interface meets level AA, with the known limitations listed below.',
    },
    method: {
      title: 'How it was assessed',
      items: [
        'Automated axe-core checks run in the end-to-end tests of the main pages, in the light and dark themes.',
        'Every control can be reached and used with the keyboard; focus is always visible.',
        'Colours come from design tokens: body text and accent text keep at least 4.5:1 contrast.',
        'Pages use landmarks, one main heading, labelled form fields and breadcrumbs.',
      ],
    },
    limits: {
      title: 'Known limitations',
      items: [
        'The interview is spoken: the interviewer’s questions are audio, with live captions and a transcript; answering requires a microphone.',
        'Some server messages that contain variable parts are shown in English only.',
        'Automated checks do not cover every WCAG criterion; the rest is checked by hand and may contain gaps.',
      ],
    },
    feedback: {
      title: 'Feedback',
      text: 'To report a barrier or ask for help, ',
      link: 'open an issue on GitHub',
    },
  },
  it: {
    title: 'Dichiarazione di accessibilità',
    updated: 'Autovalutazione del 9 novembre 2026, non verificata da terzi.',
    commitment: {
      title: 'Impegno',
      text: 'ProbeLoop punta alla conformità alle linee guida per l’accessibilità dei contenuti web (WCAG) 2.2, livello AA.',
    },
    status: {
      title: 'Stato di conformità',
      text: 'Parzialmente conforme: la maggior parte dell’interfaccia soddisfa il livello AA, con i limiti noti elencati qui sotto.',
    },
    method: {
      title: 'Come è stata valutata',
      items: [
        'Controlli automatici axe-core nei test end-to-end delle pagine principali, in tema chiaro e scuro.',
        'Ogni comando si raggiunge e si usa da tastiera; il focus è sempre visibile.',
        'I colori vengono dai token di design: testo e testo in colore d’accento hanno contrasto di almeno 4,5:1.',
        'Le pagine usano landmark, un titolo principale, campi con etichetta e breadcrumb.',
      ],
    },
    limits: {
      title: 'Limiti noti',
      items: [
        'Il colloquio è vocale: le domande dell’intervistatore sono audio, con sottotitoli e trascritto in tempo reale; per rispondere serve un microfono.',
        'Alcuni messaggi del server con parti variabili sono solo in inglese.',
        'I controlli automatici non coprono tutti i criteri WCAG; il resto è verificato a mano e può avere lacune.',
      ],
    },
    feedback: {
      title: 'Segnalazioni',
      text: 'Per segnalare una barriera o chiedere aiuto, ',
      link: 'apri una segnalazione su GitHub',
    },
  },
})
