import { expect, test, vi } from 'vitest'
import { SpeechPlayer } from './player'

test('interviewer audio uses a bounded gain without changing the analyser path', () => {
  const gain = { gain: { setTargetAtTime: vi.fn() }, connect: vi.fn() }
  const analyser = { fftSize: 1024, connect: vi.fn() }
  const context = {
    createGain: () => gain,
    createAnalyser: () => analyser,
    destination: {},
    currentTime: 2,
  }
  const player = new SpeechPlayer(context as unknown as AudioContext)
  player.setVolume(0.35)
  player.setVolume(-1)
  player.setVolume(Infinity)
  expect(analyser.connect).toHaveBeenCalledWith(gain)
  expect(gain.connect).toHaveBeenCalledWith(context.destination)
  expect(gain.gain.setTargetAtTime.mock.calls).toEqual([
    [0.35, 2, 0.02],
    [0, 2, 0.02],
  ])
})
