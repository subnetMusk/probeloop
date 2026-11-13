import { defineMessages } from '@/shared/i18n'

export const contextReviewMessages = defineMessages({
  en: {
    analysis: {
      title: 'Analysing your documents',
      waiting: 'Waiting for the analysis to start',
      leave: 'You can leave this page: the analysis continues in the background.',
      failed: 'The analysis did not succeed',
      retry: 'Try again',
    },
    missing: {
      analysing: 'Wait for the analysis to finish.',
      role: 'Complete the target profession, role and level to continue.',
    },
  },
  it: {
    analysis: {
      title: 'Analisi dei documenti',
      waiting: 'In attesa che l’analisi inizi',
      leave: 'Puoi lasciare questa pagina: l’analisi continua in background.',
      failed: 'L’analisi non è riuscita',
      retry: 'Riprova',
    },
    missing: {
      analysing: 'Attendi la fine dell’analisi.',
      role: 'Completa professione, ruolo e livello target per continuare.',
    },
  },
})
