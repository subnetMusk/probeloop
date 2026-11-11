import { useEffect, useRef } from 'react'

import { cn } from '@/shared/lib/utils'

export type SpectrumReader = (target: Uint8Array<ArrayBuffer>) => boolean

const BARS = 72
const BANDS = BARS / 4
// Speech lives roughly between 140 Hz and 4.2 kHz: bins 3 to 90 of a 1024-point FFT at 48 kHz.
const LOW_BIN = 3
const HIGH_BIN = 90
// The bands run on a logarithmic scale from the top and bottom of the ring (low voices) to its
// sides (high ones), mirrored in the four quadrants so the ring stays balanced.
const BAND_OF = Array.from({ length: BARS }, (_, i) => {
  const turn = i / BARS
  const fromVertical = Math.min(turn, Math.abs(turn - 0.5), 1 - turn)
  return Math.round((fromVertical / 0.25) * (BANDS - 1))
})
const BIN_OF = Array.from({ length: BANDS }, (_, j) =>
  Math.round(LOW_BIN * Math.pow(HIGH_BIN / LOW_BIN, j / (BANDS - 1))),
)
// Voices carry most energy in the low bands; a gentle lift of the high ones keeps the whole ring
// moving (the pre-emphasis of speech analysis).
const LIFT_OF = Array.from({ length: BANDS }, (_, j) => 1 + (1.3 * j) / (BANDS - 1))
const ATTACK = 0.5 // how fast a bar rises towards a louder frame
const RELEASE = 0.1 // and falls back afterwards

/**
 * Radial bars around an avatar that follow the voice of whoever is speaking (the audio-reactive
 * pattern of voice-agent interfaces). The bars rise with each frequency band and settle in silence;
 * with reduced motion the canvas stays empty and the tile's outline alone marks the speaker.
 */
export function VoiceRing({
  read,
  active,
  tone,
  innerRadius,
  className,
}: {
  read: SpectrumReader | null
  active: boolean
  tone: 'interviewer' | 'candidate'
  innerRadius: number // CSS pixels from the centre to the foot of the bars
  className?: string
}) {
  const canvas = useRef<HTMLCanvasElement>(null)
  const levels = useRef(new Float32Array(BARS))
  useEffect(() => {
    const element = canvas.current
    const context = element?.getContext('2d')
    if (!element || !context || !read) return
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    const size = element.clientWidth
    const ratio = window.devicePixelRatio || 1
    element.width = Math.round(size * ratio)
    element.height = Math.round(size * ratio)
    context.setTransform(ratio, 0, 0, ratio, 0, 0)
    const centre = size / 2
    const room = centre - innerRadius - 4
    const styles = getComputedStyle(document.documentElement)
    const brand = styles.getPropertyValue('--brand').trim() || '#7c3aed'
    const highlight = styles.getPropertyValue('--highlight').trim() || '#ea580c'
    let stroke: CanvasGradient | string = 'rgba(244, 244, 245, 0.9)'
    if (tone === 'interviewer') {
      if ('createConicGradient' in context) {
        const gradient = context.createConicGradient(-Math.PI / 2, centre, centre)
        gradient.addColorStop(0, brand)
        gradient.addColorStop(0.5, highlight)
        gradient.addColorStop(1, brand)
        stroke = gradient
      } else {
        stroke = brand
      }
    }
    const bins = new Uint8Array(512)
    const bars = levels.current
    let frame = 0
    const draw = () => {
      const live = active && read(bins)
      let energy = 0
      for (let i = 0; i < BARS; i++) {
        const band = BAND_OF[i] ?? 0
        const value = live ? ((bins[BIN_OF[band] ?? LOW_BIN] ?? 0) / 255) * (LIFT_OF[band] ?? 1) : 0
        const target = Math.min(1, Math.pow(Math.min(1, value), 1.7) * 1.35)
        const previous = bars[i] ?? 0
        const next = previous + (target - previous) * (target > previous ? ATTACK : RELEASE)
        bars[i] = next
        energy += next
      }
      context.clearRect(0, 0, size, size)
      context.beginPath()
      for (let i = 0; i < BARS; i++) {
        const angle = -Math.PI / 2 + (i / BARS) * Math.PI * 2
        const length = 2 + (bars[i] ?? 0) * room
        const cos = Math.cos(angle)
        const sin = Math.sin(angle)
        context.moveTo(centre + cos * innerRadius, centre + sin * innerRadius)
        context.lineTo(centre + cos * (innerRadius + length), centre + sin * (innerRadius + length))
      }
      context.lineWidth = 3
      context.lineCap = 'round'
      context.strokeStyle = stroke
      context.globalAlpha = Math.min(1, 0.35 + energy / BARS)
      context.shadowColor = tone === 'interviewer' ? brand : 'rgba(255, 255, 255, 0.6)'
      context.shadowBlur = 10
      context.stroke()
      // Keep drawing while there is voice or the bars are still settling.
      if (live || energy > 0.02) frame = requestAnimationFrame(draw)
      else context.clearRect(0, 0, size, size)
    }
    frame = requestAnimationFrame(draw)
    return () => {
      cancelAnimationFrame(frame)
    }
  }, [read, active, tone, innerRadius])
  return <canvas ref={canvas} aria-hidden className={cn('pointer-events-none', className)} />
}
