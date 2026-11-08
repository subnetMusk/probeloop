import { defineMessages } from '@/shared/i18n'

export const reviewMessages = defineMessages({
  en: {
    counts: (declared: number, total: number) =>
      `${String(declared)} of ${String(total)} facts were found word for word in your documents.`,
    declaredNote:
      'Found word for word means the quote is in the document; it does not prove the claim.',
    doubtful: {
      title: 'Facts to check',
      open: (count: number) =>
        count === 0 ? 'All checked.' : count === 1 ? '1 to check' : `${String(count)} to check`,
      none: 'Nothing to check: every fact was found word for word in your documents.',
      hint: 'Confirm what is right, exclude what is wrong, or correct it.',
    },
    fact: {
      confirm: 'Confirm',
      exclude: 'Exclude',
      correct: 'Correct',
      corrected: 'Corrected statement',
      save: 'Save correction',
      cancel: 'Cancel',
      confirmed: 'Confirmed',
      excluded: 'Excluded',
      pending: 'To check',
      quote: 'Quote from the document',
      origin: {
        declared: 'From your documents',
        inferred: 'Inferred: no quote found',
        user: 'Added by you',
      },
      warned: 'From a document with warnings',
    },
    kinds: {
      role: 'Role',
      project: 'Project',
      skill: 'Skill',
      achievement: 'Achievement',
      education: 'Education',
      certification: 'Certification',
      language: 'Language',
      other: 'Other',
      requirement: 'Requirement',
      nice_to_have: 'Nice to have',
      responsibility: 'Responsibility',
      company: 'Company',
    },
    requirements: {
      title: 'Job requirements',
      hint: 'How your documents cover the job offer, as the model reads them.',
    },
    all: {
      title: (count: number) => `All facts (${String(count)})`,
      candidate: 'About you',
      job: 'About the position',
      empty: 'No facts.',
    },
    add: {
      title: 'Add a fact the documents miss',
      subject: 'About',
      candidate: 'You',
      job: 'The position',
      statement: 'Fact',
      submit: 'Add fact',
    },
    area: {
      title: 'Your professional area',
      hint: 'Without a job offer, the interview is a getting-to-know talk for a company in this area.',
      area: 'Professional area',
      seniority: 'Seniority',
      confirm: 'Confirm area',
      save: 'Save area',
      confirmed: 'Area confirmed',
    },
    generated: 'The job offer was drafted from your description.',
    warnings: (title: string) => `Warnings for “${title}”`,
  },
  it: {
    counts: (declared: number, total: number) =>
      `${String(declared)} fatti su ${String(total)} trovati alla lettera nei tuoi documenti.`,
    declaredNote:
      'Trovato alla lettera significa che la citazione è nel documento; non dimostra l’affermazione.',
    doubtful: {
      title: 'Fatti da controllare',
      open: (count: number) =>
        count === 0
          ? 'Tutti controllati.'
          : count === 1
            ? '1 da controllare'
            : `${String(count)} da controllare`,
      none: 'Niente da controllare: ogni fatto è stato trovato alla lettera nei tuoi documenti.',
      hint: 'Conferma ciò che è giusto, escludi ciò che è sbagliato, oppure correggilo.',
    },
    fact: {
      confirm: 'Conferma',
      exclude: 'Escludi',
      correct: 'Correggi',
      corrected: 'Affermazione corretta',
      save: 'Salva correzione',
      cancel: 'Annulla',
      confirmed: 'Confermato',
      excluded: 'Escluso',
      pending: 'Da controllare',
      quote: 'Citazione dal documento',
      origin: {
        declared: 'Dai tuoi documenti',
        inferred: 'Dedotto: nessuna citazione trovata',
        user: 'Aggiunto da te',
      },
      warned: 'Da un documento con avvisi',
    },
    kinds: {
      role: 'Ruolo',
      project: 'Progetto',
      skill: 'Competenza',
      achievement: 'Risultato',
      education: 'Formazione',
      certification: 'Certificazione',
      language: 'Lingua',
      other: 'Altro',
      requirement: 'Requisito',
      nice_to_have: 'Gradito',
      responsibility: 'Responsabilità',
      company: 'Azienda',
    },
    requirements: {
      title: 'Requisiti della posizione',
      hint: 'Come i tuoi documenti coprono l’offerta, secondo la lettura del modello.',
    },
    all: {
      title: (count: number) => `Tutti i fatti (${String(count)})`,
      candidate: 'Su di te',
      job: 'Sulla posizione',
      empty: 'Nessun fatto.',
    },
    add: {
      title: 'Aggiungi un fatto che manca nei documenti',
      subject: 'Riguarda',
      candidate: 'Te',
      job: 'La posizione',
      statement: 'Fatto',
      submit: 'Aggiungi fatto',
    },
    area: {
      title: 'Il tuo settore professionale',
      hint: 'Senza offerta, il colloquio è conoscitivo per un’azienda di questo settore.',
      area: 'Settore professionale',
      seniority: 'Seniority',
      confirm: 'Conferma il settore',
      save: 'Salva il settore',
      confirmed: 'Settore confermato',
    },
    generated: 'L’offerta di lavoro è stata generata dalla tua descrizione.',
    warnings: (title: string) => `Avvisi per «${title}»`,
  },
})
