import { defineMessages } from '@/shared/i18n'

export const manageMessages = defineMessages({
  en: {
    rename: (name: string) => `Rename ${name}`,
    name: 'Profile name',
    save: 'Save name',
    cancel: 'Cancel',
    delete: (name: string) => `Delete ${name}`,
    deleteTitle: 'Delete this profile?',
    deleteText: (name: string) =>
      `“${name}” will no longer be offered. Its interviews, reports and CV checks stay with the documents they use; documents nothing else uses are deleted.`,
    confirmDelete: 'Delete profile',
  },
  it: {
    rename: (name: string) => `Rinomina ${name}`,
    name: 'Nome del profilo',
    save: 'Salva il nome',
    cancel: 'Annulla',
    delete: (name: string) => `Elimina ${name}`,
    deleteTitle: 'Eliminare questo profilo?',
    deleteText: (name: string) =>
      `«${name}» non verrà più proposto. Colloqui, report e CV check restano con i documenti che usano; i documenti che nient’altro usa vengono eliminati.`,
    confirmDelete: 'Elimina profilo',
  },
})
