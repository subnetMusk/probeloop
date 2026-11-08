import { expect, test } from '@playwright/test'
import { readFileSync } from 'node:fs'

const syntheticCV = readFileSync(
  new URL('../../backend/evals/fixtures/synthetic/context/backend-it.txt', import.meta.url),
  'utf8',
)

// The backend runs with a scripted interviewer and fake speech engines (compose.test.yaml): the
// recogniser answers "Segmento di prova di N secondi." for every segment that the real voice
// activity detector cuts from the fake microphone.
test('a voice interview from the setup page to the end of the call', async ({ page }) => {
  await page.goto('/')
  await page.getByLabel('CV text', { exact: true }).fill(syntheticCV)
  await page.getByRole('button', { name: 'Continue to resources' }).click()
  await page.getByRole('button', { name: 'Analyse documents', exact: true }).click()
  await expect(page.getByTestId('context-review')).toBeVisible({ timeout: 30_000 })
  const inferred = page
    .getByTestId('context-fact')
    .filter({ hasText: 'Unverified model interpretation.' })
  await inferred.getByRole('button', { name: 'Exclude', exact: true }).click()
  await expect(inferred).toContainText('excluded')
  await page.getByLabel('Professional area', { exact: true }).fill('Backend APIs')
  await page.getByRole('button', { name: 'Confirm area', exact: true }).click()
  await expect(page.getByText('Area confirmed', { exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Approve context and continue' }).click()
  await expect(page.getByRole('combobox', { name: 'Type', exact: true })).toContainText(
    'HR screening',
  )
  await page.getByTestId('enable-microphone').click()
  await expect(page.getByText('Say something')).toBeVisible()
  await expect(page.getByTestId('speech-status')).toContainText('Speech recognition and voice')
  await page.getByTestId('start-interview').click()

  // Joining: the resources load, then the first question is spoken.
  await expect(page.getByTestId('tile-interviewer')).toBeVisible({ timeout: 60_000 })
  const answer = page.getByTestId('answer')
  await expect(answer).toBeEnabled({ timeout: 30_000 })
  await page.getByTestId('toggle-transcript').click()
  const transcript = page.getByTestId('transcript')
  await expect(transcript).toContainText('domanda di prova numero 1')

  // The answer: microphone frames flow only between "Answer" and "End of answer".
  await answer.click()
  await expect(page.getByTestId('end-answer')).toBeVisible()
  await expect(page.getByTestId('tile-candidate')).toHaveAttribute('data-speaking', 'true')
  await page.waitForTimeout(6_000)
  await page.getByTestId('end-answer').click()
  await expect(transcript).toContainText('Segmento di prova', { timeout: 15_000 })

  // The reply is spoken, and its latency is measured in the browser.
  await expect(page.getByTestId('latency')).toBeVisible({ timeout: 15_000 })
  await expect(transcript).toContainText('domanda di prova numero 2')

  await page.getByTestId('end-call').click()
  await expect(page.getByText('The interview has ended')).toBeVisible()
  await expect(page.getByTestId('ended-summary')).toContainText('1 answer')

  // After the call the answers are transcribed again; the transcript can then be corrected.
  await page.getByTestId('review-transcript').click()
  await expect(page.getByTestId('refine-done')).toContainText('1 answers', { timeout: 30_000 })
  const answerText = page.getByTestId('answer-text')
  await expect(answerText).toContainText('Segmento di prova')
  await page.getByRole('button', { name: 'Correct' }).click()
  await page.getByLabel('Corrected answer').fill('Ho lavorato con FastAPI.')
  await page.getByRole('button', { name: 'Save correction' }).click()
  await expect(answerText).toHaveText('Ho lavorato con FastAPI.')
  await expect(page.getByText('edited')).toBeVisible()

  await page.getByRole('link', { name: 'All interviews' }).click()
  await expect(page.getByTestId('session-row').first()).toContainText('Ended')
})
