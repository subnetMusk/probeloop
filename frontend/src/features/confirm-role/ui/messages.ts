import { defineMessages } from '@/shared/i18n'

export const roleMessages = defineMessages({
  en: {
    title: 'Target role and level',
    proposal: 'Model proposal to check against your documents',
    hint: 'Check the expectations of the target role: approving the review confirms them. Level describes responsibility and supervision; difficulty changes the challenge within that level.',
    profession: 'Profession or field',
    target_role: 'Target role',
    seniority: 'Target level or training grade',
    responsibilities: 'Expected responsibilities',
    competencies: 'Competencies to explore',
    lines:
      'One per line, up to 12. These describe the target role, not claims about your abilities.',
    confirmed: 'Confirmed',
    missing: 'Complete the target profession, role and level to continue.',
  },
  it: {
    title: 'Ruolo e livello target',
    proposal: 'Proposta del modello da verificare sui documenti',
    hint: 'Verifica le aspettative del ruolo target: approvando la revisione le confermi. Il livello descrive responsabilità e supervisione; la difficoltà cambia la sfida entro quel livello.',
    profession: 'Professione o ambito',
    target_role: 'Ruolo target',
    seniority: 'Livello o grado di formazione target',
    responsibilities: 'Responsabilità attese',
    competencies: 'Competenze da esplorare',
    lines:
      'Una per riga, fino a 12. Descrivono il ruolo target, non dichiarazioni sulle tue capacità.',
    confirmed: 'Confermato',
    missing: 'Completa professione, ruolo e livello target per continuare.',
  },
})
