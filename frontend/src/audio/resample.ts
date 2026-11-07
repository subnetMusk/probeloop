/**
 * Audio conversions for the capture path. The microphone runs at the AudioContext's rate (usually
 * 44.1 or 48 kHz); the backend takes 16 kHz mono PCM16. Pure functions and a small stateful
 * class, so that the AudioWorklet and the tests run the same code.
 */

export const TARGET_RATE = 16_000

/** Windowed-sinc low-pass filter, normalised to unit gain at DC. `cutoff` is in cycles/sample. */
export function lowPassKernel(cutoff: number, taps: number): Float32Array {
  const kernel = new Float32Array(taps)
  const middle = (taps - 1) / 2
  let sum = 0
  for (let i = 0; i < taps; i++) {
    const x = i - middle
    const sinc = x === 0 ? 2 * cutoff : Math.sin(2 * Math.PI * cutoff * x) / (Math.PI * x)
    const blackman =
      0.42 -
      0.5 * Math.cos((2 * Math.PI * i) / (taps - 1)) +
      0.08 * Math.cos((4 * Math.PI * i) / (taps - 1))
    kernel[i] = sinc * blackman
    sum += sinc * blackman
  }
  for (let i = 0; i < taps; i++) kernel[i] = (kernel[i] ?? 0) / sum
  return kernel
}

/**
 * Streaming resampler: an anti-aliasing low-pass filter, then linear interpolation. Feeding a
 * signal in chunks of any size gives the same output as feeding it at once.
 */
export class Resampler {
  readonly ratio: number // input samples per output sample
  private readonly kernel: Float32Array
  private readonly history: Float32Array // the last taps - 1 input samples
  private consumed = 0 // filtered samples produced before the current chunk
  private produced = 0 // output samples produced so far
  private last = 0 // the last filtered sample of the previous chunk

  constructor(
    readonly inputRate: number,
    readonly outputRate: number = TARGET_RATE,
    taps = 63,
  ) {
    if (inputRate <= 0 || outputRate <= 0) throw new RangeError('sample rates must be positive')
    this.ratio = inputRate / outputRate
    // Downsampling needs a filter below the new Nyquist frequency; upsampling does not.
    this.kernel =
      this.ratio > 1 ? lowPassKernel((0.45 * outputRate) / inputRate, taps) : Float32Array.of(1)
    this.history = new Float32Array(this.kernel.length - 1)
  }

  process(input: Float32Array): Float32Array<ArrayBuffer> {
    const filtered = this.filter(input)
    const n = filtered.length
    const out: number[] = []
    for (;;) {
      const position = this.produced * this.ratio
      const index = Math.floor(position)
      if (index + 1 > this.consumed + n - 1) break
      const a = index < this.consumed ? this.last : (filtered[index - this.consumed] ?? 0)
      const b = filtered[index + 1 - this.consumed] ?? 0
      out.push(a + (b - a) * (position - index))
      this.produced++
    }
    if (n > 0) this.last = filtered[n - 1] ?? 0
    this.consumed += n
    return Float32Array.from(out)
  }

  private filter(input: Float32Array): Float32Array<ArrayBuffer> {
    const taps = this.kernel.length
    if (taps === 1) return Float32Array.from(input)
    const joined = new Float32Array(this.history.length + input.length)
    joined.set(this.history)
    joined.set(input, this.history.length)
    const out = new Float32Array(input.length)
    for (let i = 0; i < input.length; i++) {
      let acc = 0
      for (let k = 0; k < taps; k++) acc += (this.kernel[k] ?? 0) * (joined[i + k] ?? 0)
      out[i] = acc
    }
    this.history.set(joined.subarray(joined.length - this.history.length))
    return out
  }
}

export function floatToPcm16(samples: Float32Array): Int16Array<ArrayBuffer> {
  const out = new Int16Array(samples.length)
  for (let i = 0; i < samples.length; i++) {
    const s = Math.max(-1, Math.min(1, samples[i] ?? 0))
    out[i] = Math.round(s * 32767)
  }
  return out
}

export function pcm16ToFloat(samples: Int16Array): Float32Array<ArrayBuffer> {
  const out = new Float32Array(samples.length)
  for (let i = 0; i < samples.length; i++) out[i] = (samples[i] ?? 0) / 32768
  return out
}

/** Level in dBFS of a block of samples; -Infinity for digital silence. */
export function levelDbfs(samples: Float32Array): number {
  if (samples.length === 0) return -Infinity
  let sum = 0
  for (const s of samples) sum += s * s
  const rms = Math.sqrt(sum / samples.length)
  return rms === 0 ? -Infinity : 20 * Math.log10(rms)
}
