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
      `“${name}” will no longer be offered for new interviews. Interviews already prepared with it keep their documents.`,
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
      `«${name}» non verrà più proposto per i nuovi colloqui. I colloqui già preparati con questo profilo conservano i loro documenti.`,
    confirmDelete: 'Elimina profilo',
  },
})
