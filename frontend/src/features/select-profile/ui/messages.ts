import { defineMessages } from '@/shared/i18n'

export const profileMessages = defineMessages({
  en: {
    legend: 'Documents for this interview',
    saved: 'Saved profiles',
    loading: 'Loading the saved profiles…',
    loadError: 'The saved profiles could not be loaded.',
    noSaved: 'No saved profiles yet. A new profile keeps your CV, job offer and resources.',
    summary: {
      cv: (title: string) => `CV: ${title}`,
      noCv: 'No CV',
      offer: (title: string) => `Job offer: ${title}`,
      generated: (title: string) => `Job offer (drafted): ${title}`,
      noOffer: 'No job offer',
      resources: (count: number) => (count === 1 ? '1 resource' : `${String(count)} resources`),
      updated: (date: string) => `Updated ${date}`,
    },
    new: {
      title: 'New profile',
      description: 'Add your documents, then keep them for the next interviews.',
      name: 'Profile name',
    },
    none: {
      title: 'This interview only',
      description: 'Add your documents without saving them as a profile.',
    },
    quick: {
      title: 'No documents',
      description:
        'Set your target role and level. The interviewer has no personal background or CV to assess.',
    },
  },
  it: {
    legend: 'Documenti per questo colloquio',
    saved: 'Profili salvati',
    loading: 'Caricamento dei profili salvati…',
    loadError: 'Non è stato possibile caricare i profili salvati.',
    noSaved:
      'Ancora nessun profilo salvato. Un nuovo profilo conserva CV, offerta di lavoro e risorse.',
    summary: {
      cv: (title: string) => `CV: ${title}`,
      noCv: 'Nessun CV',
      offer: (title: string) => `Offerta: ${title}`,
      generated: (title: string) => `Offerta (generata): ${title}`,
      noOffer: 'Nessuna offerta',
      resources: (count: number) => (count === 1 ? '1 risorsa' : `${String(count)} risorse`),
      updated: (date: string) => `Aggiornato il ${date}`,
    },
    new: {
      title: 'Nuovo profilo',
      description: 'Aggiungi i tuoi documenti e conservali per i prossimi colloqui.',
      name: 'Nome del profilo',
    },
    none: {
      title: 'Solo per questo colloquio',
      description: 'Aggiungi i documenti senza salvarli in un profilo.',
    },
    quick: {
      title: 'Nessun documento',
      description:
        'Imposta ruolo e livello target. L’intervistatore non ha esperienze personali o CV da valutare.',
    },
  },
})
