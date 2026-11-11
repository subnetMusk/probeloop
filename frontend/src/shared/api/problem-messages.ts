import type { Language } from '@/shared/lib/preferences'

/**
 * Italian text of the backend's problem details and job errors. The English text is the
 * server's contract: a message that is not listed (for example one with variable parts) is
 * shown as sent.
 */
export const PROBLEMS_IT: Readonly<Record<string, string>> = {
  'Checking installed model files': 'Verifica dei file già presenti',
  'Downloading verified model files': 'Download dei file del modello',
  'Verifying model files': 'Verifica dell’integrità dei file scaricati',
  'Model installed and verified': 'Modello installato e verificato',
  'close the live interview first': 'Chiudi il colloquio attivo prima di continuare',
  'wait for background jobs to finish first':
    'Attendi il completamento dei lavori in background prima di continuare',
  "not enough space in Docker's model volume":
    'Spazio insufficiente per i modelli in Docker Desktop',
  'model checksum or size mismatch; try the download again':
    'Il file scaricato non supera la verifica. Riprova il download',
  'model download failed; try again': 'Download del modello non riuscito. Riprova',
  'model download was interrupted; try again':
    'Download interrotto. Riprova: riutilizzeremo i file già scaricati e validi',
  'model provisioning is unavailable': 'Il servizio di installazione non è raggiungibile',
  'model provisioning is not configured': 'Il servizio di installazione non è configurato',
  'configure the published Laya model URL in Settings first':
    'Indica prima nelle Impostazioni l’indirizzo del modello Laya pubblicato',
  'choose an available tool for every role in Settings':
    'Scegli uno strumento disponibile per ogni ambito nelle Impostazioni',
  'enable second transcription in Settings first':
    'Attiva prima la seconda trascrizione nelle Impostazioni',
  'Ollama is unavailable; check its connection and try again':
    'Ollama non è raggiungibile. Controlla la connessione e riprova',
  'Ollama could not download the model': 'Ollama non ha completato il download del modello',
  'Ollama download was interrupted; try again': 'Download di Ollama interrotto. Riprova',
  'selected processing tool is unavailable; restore it and resume the interview':
    'Lo strumento selezionato non è disponibile. Ripristinalo, poi riprendi il colloquio',
  'Laya is unavailable; check its model in Settings':
    'Laya non è disponibile. Controlla il modello nelle Impostazioni',
  'add a Jev API key in Settings': 'Aggiungi una chiave API di Jev nelle Impostazioni',
  'the Jev API key was rejected; check it in Settings':
    'La chiave API di Jev non è stata accettata. Controllala nelle Impostazioni',
  'Jev is unreachable; check the connection and try again':
    'Jev non è raggiungibile. Controlla la connessione e riprova',
  'Jev could not read the answer; try again': 'Jev non ha potuto leggere la risposta. Riprova',
  'paste the Jev API key without spaces': 'Incolla la chiave API di Jev senza spazi',
  'the stated-limit reader is not reachable':
    'Il lettore dei limiti dichiarati non è raggiungibile',
  'the language model is not reachable or could not be loaded':
    'Il modello linguistico non è raggiungibile o non si è caricato',
  'the speech services are not configured': 'I servizi vocali non sono configurati',
  'the speech recognition service is unreachable': 'Il riconoscimento vocale non è raggiungibile',
  'the speech recognition service is still loading its model':
    'Il riconoscimento vocale sta ancora caricando il modello',
  'the speech recognition service is not working (see its logs)':
    'Il riconoscimento vocale non funziona (vedi i suoi log)',
  'the speech recognition service did not answer in time':
    'Il riconoscimento vocale non ha risposto in tempo',
  'the speech synthesis service is unreachable': 'La sintesi vocale non è raggiungibile',
  'the speech synthesis service sent an invalid answer':
    'La sintesi vocale ha inviato una risposta non valida',
  'the speech synthesis service could not use the voice':
    'La sintesi vocale non è riuscita a usare la voce',
  'a speech service is not ready': 'Un servizio vocale non è pronto',
  'a speech service could not be checked': 'Non è stato possibile controllare un servizio vocale',
  'confirm the target role and level before approving':
    'Conferma ruolo e livello target prima di approvare',
  'confirm the target role and level': 'Conferma ruolo e livello target',
  'role profile references an unavailable fact':
    'Il profilo di ruolo fa riferimento a un fatto non più disponibile: confermalo di nuovo',
  'confirm the target role again after excluding its source facts':
    'Conferma di nuovo il ruolo target dopo aver escluso i fatti su cui si basava',
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
  'original file not available': 'File originale non disponibile',
  'the resources of a profile must be resource documents':
    'Le risorse di un profilo devono essere documenti di tipo risorsa',
  'the CV of a profile must be a CV document': 'Il CV di un profilo deve essere un documento CV',
  'the job offer of a profile must be a job offer document':
    'L’offerta di un profilo deve essere un documento di tipo offerta',
  'not found': 'Non trovato',
}

export function localizeProblem(detail: string, language: Language): string {
  return language === 'it' ? (PROBLEMS_IT[detail.trim()] ?? detail) : detail
}

export function settingsLockMessage(
  reason: 'interview' | 'background_job' | null | undefined,
  language: Language,
): string {
  if (reason === 'interview')
    return language === 'it'
      ? 'Impostazioni bloccate: chiudi il colloquio attivo per modificarle.'
      : 'Settings locked: close the active interview to change them.'
  if (reason === 'background_job')
    return language === 'it'
      ? 'Impostazioni bloccate: attendi il completamento dei lavori in background, inclusa la verifica dei modelli.'
      : 'Settings locked: wait for background work, including model verification, to finish.'
  return language === 'it'
    ? 'Attendi il completamento dell’operazione prima di modificare le impostazioni.'
    : 'Wait for the operation to finish before changing settings.'
}
