// @vitest-environment jsdom
import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'

import { api } from '@/shared/api'
import type { SessionView, TurnView } from '@/shared/api'
import { setLanguage } from '@/shared/lib/preferences'
import { Answer, Words } from './answer'
import { TurnAudioProvider } from './turn-audio'

const turn: TurnView = {
  seq: 1,
  speaker: 'candidate',
  text: 'Synthetic answer.',
  elapsed_s: 1,
  audio: null,
  words: [],
  revisions: [
    { number: 1, text: 'Synthetic answer.', source: 'stt', engine_ref: null, created_at: 0 },
  ],
  status: null,
  topic_id: null,
}
const session: SessionView = {
  id: 'synthetic',
  created_at: 0,
  status: 'ended',
  phase: null,
  difficulty: 'medium',
  language: 'en',
  modality: 'voice',
  interview_type: 'hr',
  execution_profile: 'local',
  profile_id: null,
  snapshot_id: null,
  target_duration_s: 300,
  end_reason: 'user_ended',
  failure: null,
  topics: [],
  coverage: {},
  turns: [turn],
}

beforeEach(() => {
  setLanguage('en')
})
afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

function mount(base: TurnView = turn) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const initial = { ...session, turns: [base] }
  client.setQueryData(['session', session.id], initial)
  function Content() {
    const data =
      useQuery({
        queryKey: ['session', session.id],
        queryFn: () => Promise.resolve(initial),
        staleTime: Infinity,
      }).data ?? initial
    return <Answer session={data} turn={data.turns[0] ?? base} number={1} />
  }
  render(
    <QueryClientProvider client={client}>
      <TurnAudioProvider>
        <Content />
      </TurnAudioProvider>
    </QueryClientProvider>,
  )
}

it('cancels an edit, rejects empty corrections and preserves history after saving', async () => {
  const updated = {
    ...turn,
    text: 'Corrected synthetic answer.',
    revisions: [
      ...turn.revisions,
      {
        number: 2,
        text: 'Corrected synthetic answer.',
        source: 'user_edit',
        engine_ref: null,
        created_at: 1,
      },
    ],
  }
  const edit = vi.spyOn(api, 'editAnswer').mockResolvedValue({ ...session, turns: [updated] })
  mount()
  const user = userEvent.setup()
  await user.click(screen.getByRole('button', { name: 'Correct' }))
  await user.clear(screen.getByRole('textbox', { name: 'Corrected answer' }))
  expect(screen.getByRole<HTMLButtonElement>('button', { name: 'Save correction' }).disabled).toBe(
    true,
  )
  await user.click(screen.getByRole('button', { name: 'Cancel' }))
  expect(screen.getByTestId('answer-text').textContent).toBe('Synthetic answer.')
  await user.click(screen.getByRole('button', { name: 'Correct' }))
  const field = screen.getByRole('textbox', { name: 'Corrected answer' })
  await user.clear(field)
  await user.type(field, 'Corrected synthetic answer.')
  await user.click(screen.getByRole('button', { name: 'Save correction' }))
  await waitFor(() => {
    expect(edit).toHaveBeenCalledWith('synthetic', 1, 'Corrected synthetic answer.')
  })
  expect(screen.getByTestId('answer-text').textContent).toBe('Corrected synthetic answer.')
  await user.click(screen.getByText('Revision history'))
  expect(screen.getByText('Synthetic answer.')).toBeTruthy()
})

it('highlights only recogniser probabilities below one half', () => {
  const { container } = render(
    <Words
      words={[
        { text: 'uncertain', start_s: 0, end_s: 1, probability: 0.49 },
        { text: 'known', start_s: 1, end_s: 2, probability: 0.5 },
        { text: 'unmeasured', start_s: 2, end_s: 3, probability: null },
      ]}
    />,
  )
  expect([...container.querySelectorAll('mark')].map((element) => element.textContent)).toEqual([
    'uncertain',
  ])
})

it('saves with Ctrl+Enter and cancels with Escape', async () => {
  const edit = vi.spyOn(api, 'editAnswer').mockResolvedValue({
    ...session,
    turns: [{ ...turn, text: 'Shortcut answer.' }],
  })
  mount()
  const user = userEvent.setup()
  await user.click(screen.getByRole('button', { name: 'Correct' }))
  await user.keyboard('{Escape}')
  expect(screen.queryByRole('textbox')).toBeNull()
  await user.click(screen.getByRole('button', { name: 'Correct' }))
  const field = screen.getByRole('textbox', { name: 'Corrected answer' })
  await user.clear(field)
  await user.type(field, 'Shortcut answer.')
  await user.keyboard('{Control>}{Enter}{/Control}')
  await waitFor(() => {
    expect(edit).toHaveBeenCalledWith('synthetic', 1, 'Shortcut answer.')
  })
})

it('plays the audio around a doubtful word', async () => {
  const play = vi.spyOn(HTMLMediaElement.prototype, 'play').mockResolvedValue(undefined)
  vi.spyOn(HTMLMediaElement.prototype, 'pause').mockImplementation(() => undefined)
  mount({
    ...turn,
    audio: '/api/sessions/synthetic/files/audio/turn-0001-candidate.wav',
    words: [
      { text: 'Synthetic', start_s: 0, end_s: 0.4, probability: 0.9 },
      { text: 'answer.', start_s: 2, end_s: 2.5, probability: 0.3 },
    ],
  })
  const user = userEvent.setup()
  await user.click(screen.getByRole('button', { name: /Listen to “answer\.”/ }))
  expect(play).toHaveBeenCalledTimes(1)
  const element = play.mock.contexts[0] as HTMLAudioElement
  expect(element.src).toContain('turn-0001-candidate.wav')
  expect(element.currentTime).toBeCloseTo(1.4)
  expect(screen.getByRole('button', { name: 'Pause Answer 1' }).getAttribute('aria-pressed')).toBe(
    'true',
  )
})
