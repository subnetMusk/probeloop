import { defineMessages } from '@/shared/i18n'

export const settingsMessages = defineMessages({
  en: {
    language: {
      label: 'Interview language',
      hint: 'Also used for the document analysis and the reports.',
      it: 'Italian',
      en: 'English',
      noVoice: 'No interviewer voice is installed for this language.',
    },
    type: {
      label: 'Interview type',
      technical: {
        title: 'Technical',
        description: 'Your technical knowledge and the projects you worked on.',
      },
      behavioral: {
        title: 'Behavioural',
        description: 'Past situations: what you did, decided and learned.',
      },
      hr: {
        title: 'HR screening',
        description: 'Motivation, background and expectations: a getting-to-know talk.',
      },
      mixed: {
        title: 'Mixed',
        description: 'Some technical and some behavioural questions.',
      },
    },
    difficulty: {
      label: 'Difficulty',
      easy: 'Easy',
      medium: 'Medium',
      hard: 'Hard',
    },
    duration: {
      label: 'Duration',
      minutes: (minutes: number) => `${String(minutes)} minutes`,
    },
    execution: {
      label: 'Processing',
      local: {
        title: 'On this computer',
        description: 'Local models through Ollama. Your documents, voice and transcript stay here.',
      },
      cloud: {
        title: 'ChatGPT plan',
        description:
          'OpenAI models through your ChatGPT plan, for the interviewer, the analysis and the reports.',
      },
      cloudNotice:
        'Your CV, documents, transcript and answers are sent to OpenAI, and usage counts against your ChatGPT plan. Speech recognition and synthesis always run on this computer.',
      signIn: 'Sign in with ChatGPT in Settings to use your plan.',
      settings: 'Open Settings',
    },
  },
  it: {
    language: {
      label: 'Lingua del colloquio',
      hint: 'Usata anche per l’analisi dei documenti e per i report.',
      it: 'Italiano',
      en: 'Inglese',
      noVoice: 'Nessuna voce dell’intervistatore installata per questa lingua.',
    },
    type: {
      label: 'Tipo di colloquio',
      technical: {
        title: 'Tecnico',
        description: 'Le tue conoscenze tecniche e i progetti su cui hai lavorato.',
      },
      behavioral: {
        title: 'Comportamentale',
        description: 'Situazioni passate: cosa hai fatto, deciso e imparato.',
      },
      hr: {
        title: 'Conoscitivo (HR)',
        description: 'Motivazioni, percorso e aspettative: un colloquio conoscitivo.',
      },
      mixed: {
        title: 'Misto',
        description: 'Domande in parte tecniche e in parte comportamentali.',
      },
    },
    difficulty: {
      label: 'Difficoltà',
      easy: 'Facile',
      medium: 'Media',
      hard: 'Difficile',
    },
    duration: {
      label: 'Durata',
      minutes: (minutes: number) => `${String(minutes)} minuti`,
    },
    execution: {
      label: 'Elaborazione',
      local: {
        title: 'Su questo computer',
        description: 'Modelli locali tramite Ollama. Documenti, voce e trascritto restano qui.',
      },
      cloud: {
        title: 'Piano ChatGPT',
        description:
          'Modelli OpenAI tramite il tuo piano ChatGPT, per intervistatore, analisi e report.',
      },
      cloudNotice:
        'CV, documenti, trascritto e risposte vengono inviati a OpenAI e l’utilizzo conta sul tuo piano ChatGPT. Riconoscimento e sintesi vocale restano sempre su questo computer.',
      signIn: 'Accedi con ChatGPT nelle Impostazioni per usare il tuo piano.',
      settings: 'Apri le Impostazioni',
    },
  },
})
