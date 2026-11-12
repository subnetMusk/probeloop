import { defineMessages } from '@/shared/i18n'

export const cvCheckMessages = defineMessages({
  en: {
    delete: 'Delete',
    deleteTitle: 'Delete this CV check?',
    deleteText:
      'Every version of its report is deleted, with the approved analysis. Documents stay when a saved profile or an interview uses them; documents added only for this check are deleted.',
    confirmDelete: 'Delete CV check',
    cancel: 'Cancel',
    save: 'Save as a profile',
    saveTitle: 'Save these documents as a profile',
    saveText:
      'The profile keeps the CV, the job offer and the resources of this check, and the check belongs to it.',
    name: 'Profile name',
    confirmSave: 'Save the profile',
  },
  it: {
    delete: 'Elimina',
    deleteTitle: 'Eliminare questo CV check?',
    deleteText:
      'Tutte le versioni del report vengono eliminate, con l’analisi approvata. I documenti restano se li usa un profilo salvato o un colloquio; quelli aggiunti solo per questo controllo vengono eliminati.',
    confirmDelete: 'Elimina il CV check',
    cancel: 'Annulla',
    save: 'Salva come profilo',
    saveTitle: 'Salva questi documenti come profilo',
    saveText:
      'Il profilo conserva CV, offerta e risorse di questo controllo, e il controllo gli appartiene.',
    name: 'Nome del profilo',
    confirmSave: 'Salva il profilo',
  },
})
