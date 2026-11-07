import { pcm16ToFloat } from './resample'

/**
 * Plays the interviewer's sentences back to back on the AudioContext clock.
 *
 * Each sentence is scheduled to start when the previous one ends, so there are no gaps even
 * though sentences arrive one by one while the reply is still being written. Once the server says
 * the utterance is complete (`finish`) and the last sentence has played, `onDone` runs: the page
 * then tells the server that playback finished.
 */
export class SpeechPlayer {
  private readonly sources = new Set<AudioBufferSourceNode>()
  private nextStart = 0
  private complete = false
  private onDone: (() => void) | null = null
  private onFirstStart: ((performanceTime: number) => void) | null = null

  constructor(private readonly context: AudioContext) {}

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
    source.connect(this.context.destination)
    const startAt = Math.max(this.context.currentTime + 0.05, this.nextStart)
    source.start(startAt)
    this.nextStart = startAt + buffer.duration
    this.sources.add(source)
    source.onended = () => {
      this.sources.delete(source)
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
    this.sources.clear()
    this.nextStart = 0
  }

  private checkDone(): void {
    if (this.complete && this.sources.size === 0 && this.onDone) {
      const done = this.onDone
      this.onDone = null
      done()
    }
  }
}
