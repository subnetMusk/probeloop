import { defineMessages } from '@/shared/i18n'

export const documentsMessages = defineMessages({
  en: {
    loading: 'Loading the documents of the profile…',
    loadError: 'The documents of the profile could not be loaded.',
    field: {
      upload: 'Upload a file',
      uploading: 'Uploading…',
      replace: 'Replace with a file',
      formats: 'PDF, DOCX or text, up to 10 MB. Scanned documents are not supported.',
      original: 'Original file',
      clear: 'Clear',
      edited: 'Edited: your version is saved as a new revision; the original file stays available.',
      fromFile: (name: string) => `Text extracted from ${name}. Check it and correct it if needed.`,
      warning: 'Check this document',
    },
    cv: {
      title: 'Your CV',
      description: 'Upload your CV or paste its text.',
      text: 'CV text',
    },
    offer: {
      title: 'Job offer',
      description:
        'The position you are preparing for. Without one, the interview gets to know you.',
      source: 'Job offer source',
      none: {
        title: 'No job offer',
        description: 'A getting-to-know interview for a company in your area.',
      },
      document: {
        title: 'A real job offer',
        description: 'Paste its text or upload it.',
      },
      describe: {
        title: 'Describe a role',
        description: 'A job offer is drafted from your description; edit it before continuing.',
      },
      text: 'Job offer text',
      descriptionLabel: 'Role description',
      draft: 'Draft the job offer',
      drafting: 'Drafting…',
      redraft: 'Draft again',
      drafted: 'Drafted from your description: check it and edit it.',
    },
    resources: {
      title: 'Resources',
      description:
        'Optional: project reports, a README, notes. They give the interviewer something specific to ask about. Links are never followed.',
      item: (index: number) => `Resource ${String(index)}`,
      name: 'Title',
      text: 'Resource text',
      add: 'Add a resource',
      remove: (index: number) => `Remove resource ${String(index)}`,
      limit: (max: number) => `At most ${String(max)} resources.`,
    },
    problems: {
      intro: 'To continue:',
      cv: 'add your CV',
      offer: 'add the job offer text, or choose “No job offer”',
      resourceTitle: (index: number) => `give resource ${String(index)} a title`,
      resourceContent: (index: number) => `add the text or a file to resource ${String(index)}`,
      tooMany: (max: number) => `keep at most ${String(max)} resources`,
    },
  },
  it: {
    loading: 'Caricamento dei documenti del profilo…',
    loadError: 'Non è stato possibile caricare i documenti del profilo.',
    field: {
      upload: 'Carica un file',
      uploading: 'Caricamento…',
      replace: 'Sostituisci con un file',
      formats: 'PDF, DOCX o testo, fino a 10 MB. I documenti scansionati non sono supportati.',
      original: 'File originale',
      clear: 'Svuota',
      edited:
        'Modificato: la tua versione viene salvata come nuova revisione; il file originale resta disponibile.',
      fromFile: (name: string) => `Testo estratto da ${name}. Controllalo e correggilo se serve.`,
      warning: 'Controlla questo documento',
    },
    cv: {
      title: 'Il tuo CV',
      description: 'Carica il CV o incollane il testo.',
      text: 'Testo del CV',
    },
    offer: {
      title: 'Offerta di lavoro',
      description: 'La posizione per cui ti prepari. Senza offerta, il colloquio è conoscitivo.',
      source: 'Origine dell’offerta',
      none: {
        title: 'Nessuna offerta',
        description: 'Un colloquio conoscitivo per un’azienda del tuo settore.',
      },
      document: {
        title: 'Un’offerta reale',
        description: 'Incollane il testo o caricala.',
      },
      describe: {
        title: 'Descrivi un ruolo',
        description:
          'Dalla tua descrizione viene generata un’offerta; modificala prima di continuare.',
      },
      text: 'Testo dell’offerta',
      descriptionLabel: 'Descrizione del ruolo',
      draft: 'Genera l’offerta',
      drafting: 'Generazione…',
      redraft: 'Genera di nuovo',
      drafted: 'Generata dalla tua descrizione: controllala e modificala.',
    },
    resources: {
      title: 'Risorse',
      description:
        'Facoltative: report di progetto, un README, appunti. Danno all’intervistatore spunti concreti. I link non vengono mai seguiti.',
      item: (index: number) => `Risorsa ${String(index)}`,
      name: 'Titolo',
      text: 'Testo della risorsa',
      add: 'Aggiungi una risorsa',
      remove: (index: number) => `Rimuovi la risorsa ${String(index)}`,
      limit: (max: number) => `Al massimo ${String(max)} risorse.`,
    },
    problems: {
      intro: 'Per continuare:',
      cv: 'aggiungi il tuo CV',
      offer: 'aggiungi il testo dell’offerta, oppure scegli «Nessuna offerta»',
      resourceTitle: (index: number) => `dai un titolo alla risorsa ${String(index)}`,
      resourceContent: (index: number) =>
        `aggiungi il testo o un file alla risorsa ${String(index)}`,
      tooMany: (max: number) => `tieni al massimo ${String(max)} risorse`,
    },
  },
})
