import type { Language } from '@/shared/lib/preferences'

/** One section of the guide: a heading, an optional lead and short paragraphs or steps. */
export interface GuideSection {
  id: string
  title: string
  lead?: string
  steps?: { title: string; text: string; link?: { label: string; to: GuideLink } }[]
  points?: { term: string; text: string }[]
}

export type GuideLink = '/settings' | '/setup' | '/new-interview' | '/interviews' | '/cv-checks'

export interface GuideContent {
  title: string
  description: string
  toc: string
  sections: GuideSection[]
  start: string
}

/** The guide is structured content rather than short messages, so it is chosen by language. */
export const guideContent: Record<Language, GuideContent> = {
  en: {
    title: 'How ProbeLoop works',
    description:
      'A practice job interview by voice: an AI interviewer asks about your CV and the position, listens to your answers and writes a report. This page explains the setup, each step and where to find things.',
    toc: 'On this page',
    sections: [
      {
        id: 'overview',
        title: 'At a glance',
        lead: 'Each interview goes through four stages.',
        steps: [
          {
            title: 'Prepare',
            text: 'Choose the kind of interview, add your CV, the job offer and any notes, then check what the analysis understood.',
          },
          {
            title: 'Talk',
            text: 'The interviewer asks one question at a time. You answer aloud; ProbeLoop transcribes and replies.',
          },
          {
            title: 'Review',
            text: 'Read the transcript, listen to the recording and correct the answers that were recognised badly.',
          },
          {
            title: 'Improve',
            text: 'Generate a report with strengths, gaps and suggestions, and compare it with earlier interviews.',
          },
        ],
      },
      {
        id: 'setup',
        title: 'First setup',
        lead: 'The guided setup does this for you; you can reopen it from Settings at any time.',
        steps: [
          {
            title: 'Install the speech components',
            text: 'Speech recognition and the interviewer’s voice always run on this computer. Install them once from the installation settings.',
            link: { label: 'Open the guided setup', to: '/setup' },
          },
          {
            title: 'Choose where the language models run',
            text: 'ChatGPT uses your ChatGPT plan and replies in about 5 seconds. A local model through Ollama keeps every text on this computer, but it needs a powerful machine and replies more slowly.',
            link: { label: 'Choose the processing tools', to: '/settings' },
          },
          {
            title: 'Add the optional components',
            text: 'Laya recognises, on this computer, when you say you cannot recall something. Jev does the same as a pay-as-you-go cloud service. Whisper transcribes the answers again after the interview.',
          },
          {
            title: 'Test the microphone and the voice',
            text: 'The final check of every new interview tests your microphone; Settings has a button to hear the voice.',
          },
        ],
      },
      {
        id: 'recommended',
        title: 'Recommended settings',
        points: [
          {
            term: 'With ChatGPT (fastest)',
            text: 'ChatGPT as the interviewer, Jev or Laya for stated limits, and the reconstructed transcript on: the interviewer also fixes recognition errors in your answers. Whisper is usually unnecessary.',
          },
          {
            term: 'Everything on this computer',
            text: 'The local model as the interviewer, Laya for stated limits and Whisper for a second transcription. The reconstructed transcript is not offered: local models rewrote answers in our tests.',
          },
          {
            term: 'Why it matters',
            text: 'The interviewer replies faster with ChatGPT; a local setup sends nothing outside your computer. You can change every choice later: new interviews use the new settings, earlier ones keep theirs.',
          },
        ],
      },
      {
        id: 'prepare',
        title: 'Preparing an interview',
        lead: 'New interview opens a five-step guide. Fields marked * are required.',
        points: [
          {
            term: 'Settings',
            text: 'Language, kind (technical, behavioural, HR, mixed), difficulty and duration.',
          },
          {
            term: 'Profile',
            text: 'Reuse the documents of a saved profile, create a new one, or continue without documents.',
          },
          {
            term: 'Documents',
            text: 'Drag your CV, the job offer and resources onto the upload areas, or paste the text. PDF, DOCX and text files up to 10 MB.',
          },
          {
            term: 'Fact review',
            text: 'What the analysis understood about you and the position. Correct or exclude doubtful facts: the interviewer relies on them.',
          },
          {
            term: 'Final check',
            text: 'An optional CV check, the microphone test and a summary. Start is available when the speech services are ready.',
          },
        ],
      },
      {
        id: 'call',
        title: 'During the interview',
        points: [
          {
            term: 'Getting ready',
            text: 'Before the first question every component is loaded and tested; the ring around the interviewer fills as each one becomes ready.',
          },
          {
            term: 'Answering',
            text: 'Press Answer (or Space) to start speaking and End answer (Space again) when you are done. Speak naturally: pauses do not end the answer.',
          },
          {
            term: 'Waiting for the reply',
            text: 'The ring around the interviewer shows the reply’s steps: receiving your audio, transcription, next question.',
          },
          {
            term: 'Captions and transcript',
            text: 'Captions show what is being said; the transcript button opens the whole conversation.',
          },
          {
            term: 'Pause and end',
            text: 'If a selected tool becomes unavailable the interview pauses: restore it and resume. Ending the call keeps everything said so far.',
          },
        ],
      },
      {
        id: 'after',
        title: 'After the interview',
        points: [
          {
            term: 'Transcript',
            text: 'Every answer keeps its history: the live transcript, the interviewer’s reconstruction, a second transcription and your corrections.',
          },
          {
            term: 'Flagged answers',
            text: 'Answers whose audio was partly lost, or that could not be reconstructed, are flagged. Listen to them and correct the text before the report.',
          },
          {
            term: 'Report',
            text: 'Generate report assesses the current text of each answer. You can generate new versions after corrections.',
          },
        ],
      },
      {
        id: 'library',
        title: 'CV checks and profiles',
        points: [
          {
            term: 'CV check',
            text: 'A review of your CV against the position, with the original file and its reports. Start one from CV checks, from a profile or during the final check of an interview; one you leave before it finishes waits under In progress on CV checks. Deleting it keeps the documents a profile or an interview still uses.',
          },
          {
            term: 'Profiles',
            text: 'Saved sets of documents (a CV, a job offer and resources) to reuse for interviews and CV checks. Create them from Profiles, from a CV check or while preparing an interview.',
          },
        ],
      },
      {
        id: 'privacy',
        title: 'Privacy and your data',
        points: [
          {
            term: 'Always on this computer',
            text: 'Audio, recordings, speech recognition, the voice and Laya.',
          },
          {
            term: 'Sent to a cloud service',
            text: 'With ChatGPT or Jev selected, only the text those roles need: documents and transcripts for ChatGPT, question and answer for Jev.',
          },
          {
            term: 'Backup and deletion',
            text: 'Settings › Your data exports a backup or deletes everything. Models and server configuration are not included.',
          },
        ],
      },
      {
        id: 'troubleshooting',
        title: 'If something does not work',
        points: [
          {
            term: 'The microphone is blocked',
            text: 'Allow it in the browser’s site settings (the icon beside the address), then reload the page.',
          },
          {
            term: 'The speech services are not ready',
            text: 'Install the speech components in Settings and wait for them to load; the first start after a long pause takes up to a minute.',
          },
          {
            term: 'A new interview cannot start',
            text: 'Another job is running (a report, a refinement, an analysis). The final check shows what and how far it is; it starts when that ends.',
          },
          {
            term: 'Ollama or ChatGPT is unavailable',
            text: 'Check the address of Ollama, or sign in to ChatGPT again, in Settings › Processing tools.',
          },
        ],
      },
    ],
    start: 'Prepare an interview',
  },
  it: {
    title: 'Come funziona ProbeLoop',
    description:
      'Una simulazione di colloquio di lavoro a voce: un intervistatore AI fa domande sul tuo CV e sulla posizione, ascolta le risposte e scrive un report. Qui trovi la configurazione, ogni passaggio e dove cercare le cose.',
    toc: 'In questa pagina',
    sections: [
      {
        id: 'overview',
        title: 'In breve',
        lead: 'Ogni colloquio passa per quattro fasi.',
        steps: [
          {
            title: 'Prepari',
            text: 'Scegli il tipo di colloquio, aggiungi CV, offerta di lavoro ed eventuali appunti, poi controlli cosa ha capito l’analisi.',
          },
          {
            title: 'Parli',
            text: 'L’intervistatore fa una domanda alla volta. Rispondi a voce; ProbeLoop trascrive e risponde.',
          },
          {
            title: 'Rivedi',
            text: 'Leggi il trascritto, ascolta la registrazione e correggi le risposte riconosciute male.',
          },
          {
            title: 'Migliori',
            text: 'Genera un report con punti di forza, lacune e suggerimenti, e confrontalo con i colloqui precedenti.',
          },
        ],
      },
      {
        id: 'setup',
        title: 'Prima configurazione',
        lead: 'La configurazione guidata lo fa per te; puoi riaprirla dalle Impostazioni quando vuoi.',
        steps: [
          {
            title: 'Installa i componenti vocali',
            text: 'Riconoscimento vocale e voce dell’intervistatore girano sempre su questo computer. Installali una volta dalle impostazioni di installazione.',
            link: { label: 'Apri la configurazione guidata', to: '/setup' },
          },
          {
            title: 'Scegli dove girano i modelli linguistici',
            text: 'ChatGPT usa il tuo piano ChatGPT e risponde in circa 5 secondi. Un modello locale con Ollama tiene ogni testo su questo computer, ma richiede una macchina potente e risponde più lentamente.',
            link: { label: 'Scegli gli strumenti di elaborazione', to: '/settings' },
          },
          {
            title: 'Aggiungi i componenti facoltativi',
            text: 'Laya riconosce, su questo computer, quando dichiari di non ricordare qualcosa. Jev fa lo stesso come servizio cloud a consumo. Whisper ritrascrive le risposte dopo il colloquio.',
          },
          {
            title: 'Prova microfono e voce',
            text: 'Il controllo finale di ogni nuovo colloquio prova il microfono; nelle Impostazioni c’è un pulsante per ascoltare la voce.',
          },
        ],
      },
      {
        id: 'recommended',
        title: 'Impostazioni consigliate',
        points: [
          {
            term: 'Con ChatGPT (la più veloce)',
            text: 'ChatGPT come intervistatore, Jev o Laya per i limiti dichiarati e la trascrizione ricostruita attiva: l’intervistatore corregge anche gli errori di riconoscimento delle tue risposte. Whisper di solito non serve.',
          },
          {
            term: 'Tutto su questo computer',
            text: 'Il modello locale come intervistatore, Laya per i limiti dichiarati e Whisper per la seconda trascrizione. La trascrizione ricostruita non è disponibile: nei test i modelli locali riscrivevano le risposte.',
          },
          {
            term: 'Perché conta',
            text: 'Con ChatGPT l’intervistatore risponde più in fretta; in locale nulla esce dal tuo computer. Puoi cambiare ogni scelta in seguito: i nuovi colloqui usano le nuove impostazioni, quelli già fatti mantengono le loro.',
          },
        ],
      },
      {
        id: 'prepare',
        title: 'Preparare un colloquio',
        lead: 'Nuovo colloquio apre una procedura in cinque passi. I campi con * sono obbligatori.',
        points: [
          {
            term: 'Impostazioni',
            text: 'Lingua, tipo (tecnico, comportamentale, HR, misto), difficoltà e durata.',
          },
          {
            term: 'Profilo',
            text: 'Riusa i documenti di un profilo salvato, creane uno nuovo oppure procedi senza documenti.',
          },
          {
            term: 'Documenti',
            text: 'Trascina CV, offerta e risorse nelle aree di caricamento, oppure incolla il testo. PDF, DOCX e file di testo fino a 10 MB.',
          },
          {
            term: 'Revisione dei fatti',
            text: 'Ciò che l’analisi ha capito di te e della posizione. Correggi o escludi i fatti dubbi: l’intervistatore si basa su questi.',
          },
          {
            term: 'Controllo finale',
            text: 'Un CV check facoltativo, la prova del microfono e un riepilogo. L’avvio è disponibile quando i servizi vocali sono pronti.',
          },
        ],
      },
      {
        id: 'call',
        title: 'Durante il colloquio',
        points: [
          {
            term: 'Preparazione',
            text: 'Prima della prima domanda ogni componente viene caricato e provato; l’anello attorno all’intervistatore si riempie man mano che sono pronti.',
          },
          {
            term: 'Rispondere',
            text: 'Premi Rispondi (o Spazio) per iniziare a parlare e Fine risposta (di nuovo Spazio) quando hai finito. Parla con naturalezza: le pause non chiudono la risposta.',
          },
          {
            term: 'Attesa della domanda',
            text: 'L’anello attorno all’intervistatore mostra i passi della risposta: ricezione audio, trascrizione, prossima domanda.',
          },
          {
            term: 'Sottotitoli e trascritto',
            text: 'I sottotitoli mostrano ciò che si sta dicendo; il pulsante del trascritto apre l’intera conversazione.',
          },
          {
            term: 'Pausa e fine',
            text: 'Se uno strumento scelto non è più disponibile, il colloquio va in pausa: ripristinalo e riprendi. Chiudendo la chiamata resta tutto ciò che è stato detto.',
          },
        ],
      },
      {
        id: 'after',
        title: 'Dopo il colloquio',
        points: [
          {
            term: 'Trascritto',
            text: 'Ogni risposta conserva la sua storia: il testo dal vivo, la ricostruzione dell’intervistatore, la seconda trascrizione e le tue correzioni.',
          },
          {
            term: 'Risposte segnalate',
            text: 'Le risposte con audio in parte perso, o che non è stato possibile ricostruire, sono segnalate. Ascoltale e correggi il testo prima del report.',
          },
          {
            term: 'Report',
            text: 'Genera report valuta il testo attuale di ogni risposta. Dopo le correzioni puoi generarne nuove versioni.',
          },
        ],
      },
      {
        id: 'library',
        title: 'CV check e profili',
        points: [
          {
            term: 'CV check',
            text: 'Una revisione del tuo CV rispetto alla posizione, con il file originale e i suoi report. Avviala da CV check, da un profilo o durante il controllo finale di un colloquio; se la lasci prima che finisca, la ritrovi in In corso su CV check. Eliminarla conserva i documenti che un profilo o un colloquio usano ancora.',
          },
          {
            term: 'Profili',
            text: 'Insiemi di documenti salvati (CV, offerta e risorse) da riusare in colloqui e CV check. Creali da Profili, da un CV check o mentre prepari un colloquio.',
          },
        ],
      },
      {
        id: 'privacy',
        title: 'Privacy e dati',
        points: [
          {
            term: 'Sempre su questo computer',
            text: 'Audio, registrazioni, riconoscimento vocale, voce e Laya.',
          },
          {
            term: 'Inviato a un servizio cloud',
            text: 'Con ChatGPT o Jev selezionati, solo il testo che serve a quegli ambiti: documenti e trascritti per ChatGPT, domanda e risposta per Jev.',
          },
          {
            term: 'Backup ed eliminazione',
            text: 'Impostazioni › I tuoi dati esporta un backup o elimina tutto. Modelli e configurazione del server non sono inclusi.',
          },
        ],
      },
      {
        id: 'troubleshooting',
        title: 'Se qualcosa non funziona',
        points: [
          {
            term: 'Il microfono è bloccato',
            text: 'Consentilo nelle impostazioni del sito del browser (l’icona accanto all’indirizzo), poi ricarica la pagina.',
          },
          {
            term: 'I servizi vocali non sono pronti',
            text: 'Installa i componenti vocali dalle Impostazioni e attendi il caricamento; il primo avvio dopo una lunga pausa richiede fino a un minuto.',
          },
          {
            term: 'Un nuovo colloquio non parte',
            text: 'È in corso un’altra elaborazione (un report, una rifinitura, un’analisi). Il controllo finale mostra quale e a che punto è; si parte quando finisce.',
          },
          {
            term: 'Ollama o ChatGPT non sono disponibili',
            text: 'Controlla l’indirizzo di Ollama, oppure accedi di nuovo a ChatGPT, in Impostazioni › Strumenti di elaborazione.',
          },
        ],
      },
    ],
    start: 'Prepara un colloquio',
  },
}
