import { describe, expect, it } from 'vitest'

import {
  Resampler,
  floatToPcm16,
  levelDbfs,
  lowPassKernel,
  pcm16ToFloat,
  TARGET_RATE,
} from './resample'

function sine(frequency: number, rate: number, seconds: number, amplitude = 0.5): Float32Array {
  const out = new Float32Array(Math.round(rate * seconds))
  for (let i = 0; i < out.length; i++)
    out[i] = amplitude * Math.sin((2 * Math.PI * frequency * i) / rate)
  return out
}

function rms(samples: Float32Array): number {
  let sum = 0
  for (const s of samples) sum += s * s
  return Math.sqrt(sum / samples.length)
}

/** Amplitude of one frequency component, by correlation with a sine and a cosine. */
function component(samples: Float32Array, frequency: number, rate: number): number {
  let re = 0
  let im = 0
  for (let i = 0; i < samples.length; i++) {
    const phase = (2 * Math.PI * frequency * i) / rate
    re += (samples[i] ?? 0) * Math.cos(phase)
    im += (samples[i] ?? 0) * Math.sin(phase)
  }
  return (2 * Math.hypot(re, im)) / samples.length
}

function chunked(resampler: Resampler, input: Float32Array, sizes: number[]): Float32Array {
  const parts: number[] = []
  let offset = 0
  let turn = 0
  while (offset < input.length) {
    const size = sizes[turn++ % sizes.length] ?? 128
    parts.push(...resampler.process(input.subarray(offset, offset + size)))
    offset += size
  }
  return Float32Array.from(parts)
}

describe('lowPassKernel', () => {
  it('has unit gain at DC', () => {
    expect(lowPassKernel(0.15, 63).reduce((a, b) => a + b, 0)).toBeCloseTo(1, 6)
  })
})

describe('Resampler', () => {
  it.each([48_000, 44_100, 32_000])(
    'turns one second at %i Hz into one second at 16 kHz',
    (rate) => {
      const out = new Resampler(rate).process(sine(440, rate, 1))
      expect(Math.abs(out.length - TARGET_RATE)).toBeLessThanOrEqual(2)
    },
  )

  it('gives the same output whatever the chunk sizes', () => {
    const input = sine(700, 48_000, 0.5)
    const whole = new Resampler(48_000).process(input)
    const pieces = chunked(new Resampler(48_000), input, [128, 1, 333, 4096, 7])
    expect(pieces.length).toBe(whole.length)
    for (let i = 0; i < whole.length; i++) expect(pieces[i]).toBeCloseTo(whole[i] ?? 0, 5)
  })

  it('keeps speech frequencies', () => {
    const out = new Resampler(48_000).process(sine(1_000, 48_000, 1)).subarray(200)
    expect(component(out, 1_000, TARGET_RATE)).toBeCloseTo(0.5, 1)
  })

  it('removes frequencies above the new Nyquist limit instead of folding them back', () => {
    const out = new Resampler(48_000).process(sine(12_000, 48_000, 1)).subarray(200)
    expect(rms(out)).toBeLessThan(0.01) // the input RMS is 0.35
    expect(component(out, 4_000, TARGET_RATE)).toBeLessThan(0.01) // where 12 kHz would alias
  })

  it('keeps a constant level', () => {
    const out = new Resampler(44_100).process(new Float32Array(44_100).fill(0.25)).subarray(100)
    for (const s of out) expect(s).toBeCloseTo(0.25, 4)
  })

  it('passes 16 kHz through unchanged', () => {
    const input = sine(300, TARGET_RATE, 0.1)
    expect(Array.from(new Resampler(TARGET_RATE).process(input))).toEqual(
      Array.from(input.subarray(0, input.length - 1)),
    )
  })

  it('rejects invalid rates', () => {
    expect(() => new Resampler(0)).toThrow(RangeError)
  })
})

describe('PCM16 conversion', () => {
  it('scales and clamps', () => {
    expect(Array.from(floatToPcm16(Float32Array.of(0, 0.5, -0.5, 1, -1, 2, -2)))).toEqual([
      0, 16384, -16383, 32767, -32767, 32767, -32767,
    ])
  })

  it('round-trips within one step', () => {
    const input = sine(220, TARGET_RATE, 0.05)
    const back = pcm16ToFloat(floatToPcm16(input))
    for (let i = 0; i < input.length; i++) expect(back[i]).toBeCloseTo(input[i] ?? 0, 4)
  })
})

describe('levelDbfs', () => {
  it('measures a full-scale sine at about -3 dBFS', () => {
    expect(levelDbfs(sine(1_000, 48_000, 0.1, 1))).toBeCloseTo(-3.01, 1)
  })

  it('reports silence as -Infinity', () => {
    expect(levelDbfs(new Float32Array(128))).toBe(-Infinity)
  })
})
