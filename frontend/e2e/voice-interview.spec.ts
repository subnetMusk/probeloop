import { expect, test } from '@playwright/test'

// The backend runs with a scripted interviewer and fake speech engines (compose.test.yaml): the
// recogniser answers "Segmento di prova di N secondi." for every segment that the real voice
// activity detector cuts from the fake microphone.
test('a voice interview from the setup page to the end of the call', async ({ page }) => {
  await page.goto('/')
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
})
