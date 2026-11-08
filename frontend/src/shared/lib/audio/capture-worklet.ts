/**
 * AudioWorklet that turns the microphone into 16 kHz mono PCM16 frames of 100 ms.
 *
 * It runs on the audio rendering thread. Each frame goes to the main thread with its level, as a
 * transferable buffer; the main thread decides whether to send it (only while answering).
 */
import { Resampler, TARGET_RATE, floatToPcm16, levelDbfs } from './resample'

declare const sampleRate: number
declare class AudioWorkletProcessor {
  readonly port: MessagePort
}
declare function registerProcessor(
  name: string,
  processor: new () => AudioWorkletProcessor & {
    process(inputs: Float32Array[][]): boolean
  },
): void

export interface CaptureFrame {
  pcm: ArrayBuffer // Int16 samples at 16 kHz
  level: number // dBFS of the frame
}

const FRAME_SAMPLES = TARGET_RATE / 10

class CaptureProcessor extends AudioWorkletProcessor {
  private readonly resampler = new Resampler(sampleRate, TARGET_RATE)
  private frame = new Float32Array(FRAME_SAMPLES)
  private filled = 0

  process(inputs: Float32Array[][]): boolean {
    const channels = inputs[0]
    const first = channels?.[0]
    if (!channels || !first) return true
    let mono = first
    if (channels.length > 1) {
      mono = new Float32Array(first.length)
      for (const channel of channels)
        for (let i = 0; i < mono.length; i++)
          mono[i] = (mono[i] ?? 0) + (channel[i] ?? 0) / channels.length
    }
    const resampled = this.resampler.process(mono)
    let offset = 0
    while (offset < resampled.length) {
      const take = Math.min(FRAME_SAMPLES - this.filled, resampled.length - offset)
      this.frame.set(resampled.subarray(offset, offset + take), this.filled)
      this.filled += take
      offset += take
      if (this.filled === FRAME_SAMPLES) {
        const pcm = floatToPcm16(this.frame)
        const message: CaptureFrame = { pcm: pcm.buffer, level: levelDbfs(this.frame) }
        this.port.postMessage(message, [pcm.buffer])
        this.frame = new Float32Array(FRAME_SAMPLES)
        this.filled = 0
      }
    }
    return true
  }
}

registerProcessor('probeloop-capture', CaptureProcessor)
