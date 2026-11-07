import { pcm16ToFloat } from './resample'

/**
 * Plays the interviewer's sentences back to back on the AudioContext clock.
 *
 * Each sentence is scheduled to start when the previous one ends, so there are no gaps even
 * though sentences arrive one by one while the reply is still being written. Once the server says
 * the utterance is complete (`finish`) and the last sentence has played, `onDone` runs: the page
 * then tells the server that playback finished.
 *
 * Everything goes through an analyser, so the page can animate the interviewer while it speaks.
 */
export class SpeechPlayer {
  private readonly sources = new Set<AudioBufferSourceNode>()
  private readonly analyser: AnalyserNode
  private readonly samples: Float32Array<ArrayBuffer>
  private readonly listeners = new Set<(playing: boolean) => void>()
  private nextStart = 0
  private complete = false
  private onDone: (() => void) | null = null
  private onFirstStart: ((performanceTime: number) => void) | null = null

  constructor(private readonly context: AudioContext) {
    this.analyser = context.createAnalyser()
    this.analyser.fftSize = 1024
    this.analyser.connect(context.destination)
    this.samples = new Float32Array(this.analyser.fftSize)
  }

  /** A new utterance. `onFirstStart` receives when its first audio starts, in performance time. */
  begin(onFirstStart: (performanceTime: number) => void): void {
    this.complete = false
    this.onDone = null
    this.onFirstStart = onFirstStart
  }

  enqueue(pcm: Int16Array, sampleRate: number): void {
    if (pcm.length === 0) return
    const buffer = this.context.createBuffer(1, pcm.length, sampleRate)
    buffer.copyToChannel(pcm16ToFloat(pcm), 0)
    const source = this.context.createBufferSource()
    source.buffer = buffer
    source.connect(this.analyser)
    const startAt = Math.max(this.context.currentTime + 0.05, this.nextStart)
    source.start(startAt)
    this.nextStart = startAt + buffer.duration
    this.sources.add(source)
    if (this.sources.size === 1) this.notify(true)
    source.onended = () => {
      this.sources.delete(source)
      if (this.sources.size === 0) this.notify(false)
      this.checkDone()
    }
    if (this.onFirstStart) {
      const delayMs = (startAt - this.context.currentTime) * 1000
      this.onFirstStart(performance.now() + delayMs)
      this.onFirstStart = null
    }
  }

  /** No more sentences will come for this utterance. */
  finish(onDone: () => void): void {
    this.complete = true
    this.onDone = onDone
    this.checkDone()
  }

  /** Silence everything at once (pause, end of the call). */
  stop(): void {
    this.onDone = null
    this.onFirstStart = null
    for (const source of this.sources) {
      source.onended = null
      source.stop()
    }
    if (this.sources.size > 0) this.notify(false)
    this.sources.clear()
    this.nextStart = 0
  }

  /** Loudness of what is playing now, from 0 to about 1. */
  level(): number {
    if (this.sources.size === 0) return 0
    this.analyser.getFloatTimeDomainData(this.samples)
    let sum = 0
    for (const s of this.samples) sum += s * s
    return Math.min(1, Math.sqrt(sum / this.samples.length) * 4)
  }

  /** Called with true when speech starts and false when it stops. Returns an unsubscribe. */
  subscribe(listener: (playing: boolean) => void): () => void {
    this.listeners.add(listener)
    return () => {
      this.listeners.delete(listener)
    }
  }

  private notify(playing: boolean): void {
    for (const listener of this.listeners) listener(playing)
  }

  private checkDone(): void {
    if (this.complete && this.sources.size === 0 && this.onDone) {
      const done = this.onDone
      this.onDone = null
      done()
    }
  }
}
