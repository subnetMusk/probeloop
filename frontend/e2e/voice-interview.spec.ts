import { expect, test } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import { readFileSync } from 'node:fs'
import { setTheme } from './helpers/theme.js'
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('probeloop.preferences', JSON.stringify({ language: 'en' }))
  })
})

const syntheticCV = readFileSync(
  new URL('../../backend/evals/fixtures/synthetic/context/backend-it.txt', import.meta.url),
  'utf8',
)

// The backend runs with a scripted interviewer and fake speech engines (compose.test.yaml): the
// recogniser answers "Segmento di prova di N secondi." for every segment that the real voice
// activity detector cuts from the fake microphone.
test('a voice interview from the preparation to the end of the call', async ({ page }) => {
  await page.goto('/settings')
  await page.evaluate(() => {
    sessionStorage.clear()
  })
  await page.goto('/new-interview')
  const next = page.getByTestId('step-continue')
  await page.getByRole('radio', { name: 'Italian', exact: true }).click()
  await page.getByRole('radio', { name: 'HR screening', exact: true }).click()
  await next.click()
  await page.getByRole('radio', { name: 'This interview only', exact: true }).click()
  await next.click()
  await page.getByRole('textbox', { name: 'CV text', exact: true }).fill(syntheticCV)
  await next.click()
  await expect(page.getByTestId('context-review')).toBeVisible({ timeout: 30_000 })
  const inferred = page
    .getByTestId('doubtful-facts')
    .getByTestId('context-fact')
    .filter({ hasText: 'Unverified model interpretation.' })
  await inferred.getByRole('button', { name: 'Exclude', exact: true }).click()
  await expect(inferred.getByRole('button', { name: 'Exclude', exact: true })).toHaveAttribute(
    'aria-pressed',
    'true',
  )
  await page.getByRole('textbox', { name: 'Professional area', exact: true }).fill('Backend APIs')
  await page.getByRole('button', { name: 'Confirm area', exact: true }).click()
  await expect(page.getByText('Area confirmed', { exact: true })).toBeVisible()
  await next.click()
  await expect(page).toHaveURL(/\/new-interview\/final-check$/)
  await page.getByTestId('enable-microphone').click()
  await expect(page.getByText('Say something')).toBeVisible()
  await expect(page.getByTestId('speech-status')).toContainText('Speech recognition and voice')
  await next.click()

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
  // Ending persists the transcript and mixes the complete recording before publishing completion.
  await expect(page.getByText('The interview has ended')).toBeVisible({ timeout: 30_000 })
  await expect(page.getByTestId('ended-summary')).toContainText('1 answer')

  // After the call the answers are transcribed again; the transcript can then be corrected.
  await page.getByTestId('review-transcript').click()
  await expect(page.getByTestId('refine-done')).toContainText('1 answer', { timeout: 30_000 })
  const answerText = page.getByTestId('answer-text')
  await expect(answerText).toContainText('Segmento di prova')
  await page.getByRole('button', { name: 'Correct' }).click()
  await page.getByLabel('Corrected answer').fill('Ho lavorato con FastAPI.')
  await page.getByRole('button', { name: 'Save correction' }).click()
  await expect(answerText).toHaveText('Ho lavorato con FastAPI.')
  await expect(page.getByText('edited')).toBeVisible()
  for (const theme of ['light', 'dark']) {
    await setTheme(page, theme)
    const scan = await new AxeBuilder({ page }).analyze()
    expect(
      scan.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical'),
    ).toEqual([])
  }
  await page.screenshot({ path: 'test-results/transcript.png', fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  const metadata = await page.locator('main > header p').first().boundingBox()
  expect(metadata?.height).toBeLessThanOrEqual(48)
  expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)).toBe(
    false,
  )
  await page.screenshot({ path: 'test-results/transcript-mobile.png' })
  await page.setViewportSize({ width: 1280, height: 720 })

  // The report assesses the corrected revision in the background (scripted evaluator).
  const reports = page.getByTestId('interview-report-panel')
  await reports.getByRole('button', { name: 'Generate report' }).click()
  const first = reports.getByRole('link', { name: /^Open report v1 / })
  await expect(first).toBeVisible({ timeout: 60_000 })
  await first.click()
  const content = page.getByTestId('report-content')
  await expect(content).toContainText('Synthetic evidence-based practice summary.')
  // Quotations show the transcript's own words, between the first and last matched word.
  await expect(content).toContainText('“Ho lavorato con FastAPI”')
  const types = { md: 'text/markdown', json: 'application/json', pdf: 'application/pdf' }
  for (const [format, type] of Object.entries(types)) {
    const link = page.getByRole('link', { name: format.toUpperCase(), exact: true })
    const href = await link.getAttribute('href')
    expect(href).not.toBeNull()
    const download = await page.request.get(href ?? '')
    expect(download.ok()).toBe(true)
    expect(download.headers()['content-type']).toContain(type)
    if (format === 'md') {
      const markdown = await download.text()
      const headings = [...markdown.matchAll(/^## (.+)$/gm)].map((match) => match[1])
      expect(headings.slice(0, 8)).toEqual([
        'Overview',
        'What to improve',
        'Strengths',
        'Question by question',
        'Job requirements',
        'How you spoke',
        'Questions to practise',
        'Technical details',
      ])
      expect(markdown).toContain('Ho lavorato con FastAPI.')
      expect(markdown).toContain('Questa è la domanda di prova numero 1?')
    }
  }
  for (const theme of ['light', 'dark']) {
    await setTheme(page, theme)
    const scan = await new AxeBuilder({ page }).analyze()
    expect(
      scan.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical'),
    ).toEqual([])
  }
  await page.screenshot({ path: 'test-results/interview-report.png', fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth)).toBe(
    false,
  )
  await page.screenshot({ path: 'test-results/interview-report-mobile.png' })
  await page.setViewportSize({ width: 1280, height: 720 })

  // Regenerating keeps the earlier version.
  await page.goBack()
  await reports.getByRole('button', { name: 'Generate report' }).click()
  await expect(reports.getByRole('link', { name: /^Open report v2 / })).toBeVisible({
    timeout: 60_000,
  })
  await expect(first).toBeVisible()

  await page.getByRole('link', { name: 'All interviews' }).click()
  const latest = page.getByTestId('interview-row').first()
  await expect(latest).toContainText('HR screening')
  await expect(latest).toContainText('1 answer')
})
