import { defineMessages } from '@/shared/i18n'

export const newCvCheckMessages = defineMessages({
  en: {
    eyebrow: 'CV check',
    title: 'New CV check',
    description:
      'Check how a CV reads against a job offer, or against the role it targets. No interview is needed.',
    source: 'Documents to check',
    saved: 'Saved profiles',
    loading: 'Loading the saved profiles…',
    noCv: 'This profile has no CV.',
    oneOff: {
      title: 'Documents for this check',
      description: 'Add a CV and, if you want, a job offer or resources.',
    },
    saveAs: 'Save as a profile (optional)',
    saveAsHint: 'Leave it empty to use the documents for this check only.',
    analyse: 'Analyse the documents',
    analysing: 'Starting the analysis…',
    missing: {
      source: 'Choose the documents to check.',
      uploading: 'Wait for the uploads to finish.',
    },
    review: {
      title: 'Review the analysis',
      description: 'Check the target role and the facts the analysis found, then check the CV.',
      approve: 'Approve and check the CV',
      back: 'Back to the documents',
      approving: 'Starting the check…',
      noCv: 'There is no CV among these documents, so there is nothing to check.',
    },
  },
  it: {
    eyebrow: 'CV check',
    title: 'Nuovo CV check',
    description:
      'Controlla come si legge un CV rispetto a un’offerta o al ruolo a cui punta. Non serve un colloquio.',
    source: 'Documenti da controllare',
    saved: 'Profili salvati',
    loading: 'Caricamento dei profili salvati…',
    noCv: 'Questo profilo non ha un CV.',
    oneOff: {
      title: 'Documenti per questo controllo',
      description: 'Aggiungi un CV e, se vuoi, un’offerta o delle risorse.',
    },
    saveAs: 'Salva come profilo (facoltativo)',
    saveAsHint: 'Lascialo vuoto per usare i documenti solo per questo controllo.',
    analyse: 'Analizza i documenti',
    analysing: 'Avvio dell’analisi…',
    missing: {
      source: 'Scegli i documenti da controllare.',
      uploading: 'Attendi la fine dei caricamenti.',
    },
    review: {
      title: 'Revisione dell’analisi',
      description: 'Verifica il ruolo target e i fatti trovati dall’analisi, poi controlla il CV.',
      approve: 'Approva e controlla il CV',
      back: 'Torna ai documenti',
      approving: 'Avvio del controllo…',
      noCv: 'Tra questi documenti non c’è un CV, quindi non c’è nulla da controllare.',
    },
  },
})
