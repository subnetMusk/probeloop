import type { Language } from '@/shared/lib/preferences'

/**
 * Italian text of the backend's problem details and job errors. The English text is the
 * server's contract: a message that is not listed (for example one with variable parts) is
 * shown as sent.
 */
export const PROBLEMS_IT: Readonly<Record<string, string>> = {
  'CV review could not be completed; try again':
    'Non è stato possibile completare la revisione del CV; riprova',
  'interview review could not be completed; try again':
    'Non è stato possibile completare la valutazione del colloquio; riprova',
  'documents or answers exceed the evaluator context; prepare shorter resources or answers':
    'Documenti o risposte superano il contesto del valutatore: usa risorse o risposte più brevi',
  'interview not found': 'Colloquio non trovato',
  'the documents could not be analysed': 'Non è stato possibile analizzare i documenti',
  'speech recognition is not configured': 'Il riconoscimento vocale non è configurato',
  'end the interview before generating a report':
    'Termina il colloquio prima di generare il report',
  'the interview has no answers to assess': 'Il colloquio non contiene risposte da valutare',
  'the approved context has no CV': 'Il contesto approvato non contiene un CV',
  'the interview is not over': 'Il colloquio non è terminato',
  'model unavailable': 'Modello non disponibile',
  'the file is larger than 10 MB': 'Il file supera i 10 MB',
  'describe the position in a few words first': 'Descrivi prima la posizione in poche parole',
  'add at least a CV, a job offer or a resource':
    'Aggiungi almeno un CV, un’offerta di lavoro o una risorsa',
  'the statement cannot be empty': 'L’affermazione non può essere vuota',
  'a correction needs the corrected statement': 'Una correzione richiede l’affermazione corretta',
  'the area cannot be empty': 'L’area non può essere vuota',
  'confirm the professional area before approving':
    'Conferma l’area professionale prima di approvare',
  'close live interviews and wait for background jobs first':
    'Chiudi i colloqui in corso e attendi la fine delle elaborazioni',
  'backup no longer available': 'Backup non più disponibile',
  'the cloud profile is not configured': 'Il profilo cloud non è configurato',
  'sign in with ChatGPT first': 'Accedi prima con ChatGPT',
  'sign in with ChatGPT again in Settings': 'Accedi di nuovo con ChatGPT nelle Impostazioni',
  'allow ProbeLoop to use your ChatGPT plan in Settings':
    'Consenti a ProbeLoop di usare il tuo piano ChatGPT nelle Impostazioni',
  'ChatGPT sign-in could not be renewed; try again':
    'Non è stato possibile rinnovare l’accesso a ChatGPT; riprova',
  'ChatGPT plan usage limit reached; see your ChatGPT usage settings':
    'Limite di utilizzo del piano ChatGPT raggiunto; controlla l’utilizzo nelle impostazioni di ChatGPT',
  'this ChatGPT account cannot use its plan in ProbeLoop':
    'Questo account ChatGPT non può usare il suo piano in ProbeLoop',
  'unknown job kind': 'Tipo di elaborazione sconosciuto',
  'report not found': 'Report non trovato',
  'session not found': 'Colloquio non trovato',
  'approved context not found': 'Contesto approvato non trovato',
  'profile not found': 'Profilo non trovato',
  'document not found': 'Documento non trovato',
  'not found': 'Non trovato',
}

export function localizeProblem(detail: string, language: Language): string {
  return language === 'it' ? (PROBLEMS_IT[detail.trim()] ?? detail) : detail
}
