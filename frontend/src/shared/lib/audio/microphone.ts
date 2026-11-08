import captureWorkletUrl from './capture-worklet.ts?worker&url'
import type { CaptureFrame } from './capture-worklet'

export type MicrophoneProblem = 'denied' | 'not_found' | 'unsupported' | 'failed'

export class MicrophoneError extends Error {
  constructor(readonly problem: MicrophoneProblem) {
    super(problem)
  }
}

/**
 * The microphone, captured as 16 kHz PCM16 frames of 100 ms.
 *
 * The track stays open for the whole interview; frames reach `onFrame` only while `streaming` is
 * on, which is between "answer" and "end of answer". The server drops anything else anyway.
 */
export class Microphone {
  private streaming = false
  private onFrame: (pcm: Int16Array) => void = () => undefined
  onLevel: (dbfs: number) => void = () => undefined
  onLost: () => void = () => undefined

  private constructor(
    private readonly stream: MediaStream,
    private readonly source: MediaStreamAudioSourceNode,
    private readonly node: AudioWorkletNode,
  ) {
    node.port.onmessage = (event: MessageEvent<CaptureFrame>) => {
      this.onLevel(event.data.level)
      if (this.streaming) this.onFrame(new Int16Array(event.data.pcm))
    }
    for (const track of stream.getAudioTracks()) {
      track.addEventListener('ended', () => {
        this.onLost()
      })
    }
  }

  static async open(context: AudioContext): Promise<Microphone> {
    if (!('mediaDevices' in navigator) || !('audioWorklet' in context)) {
      throw new MicrophoneError('unsupported')
    }
    let stream: MediaStream
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          channelCount: 1,
        },
      })
    } catch (error) {
      const name = error instanceof DOMException ? error.name : ''
      if (name === 'NotAllowedError' || name === 'SecurityError')
        throw new MicrophoneError('denied')
      if (name === 'NotFoundError' || name === 'OverconstrainedError')
        throw new MicrophoneError('not_found')
      throw new MicrophoneError('failed')
    }
    await context.audioWorklet.addModule(captureWorkletUrl)
    const source = context.createMediaStreamSource(stream)
    const node = new AudioWorkletNode(context, 'probeloop-capture', {
      numberOfInputs: 1,
      numberOfOutputs: 0,
      channelCount: 1,
      channelCountMode: 'explicit',
    })
    source.connect(node)
    return new Microphone(stream, source, node)
  }

  /** Send frames to `handler` from now on (answer), or stop with `null`. */
  forwardFrames(handler: ((pcm: Int16Array) => void) | null): void {
    this.streaming = handler !== null
    this.onFrame = handler ?? (() => undefined)
  }

  get label(): string {
    return this.stream.getAudioTracks()[0]?.label ?? ''
  }

  close(): void {
    this.forwardFrames(null)
    this.source.disconnect()
    this.node.port.onmessage = null
    for (const track of this.stream.getTracks()) track.stop()
  }
}
