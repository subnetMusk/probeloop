import { expect, test } from '@playwright/test'
import { fileURLToPath } from 'node:url'

// Explicit opt-in: this uses real models, speech services and the primary data volume.
// It only adds synthetic records. It never deletes data or changes account settings.
test.skip(
  process.env.PROBELOOP_LIVE_ACCEPTANCE !== '1',
  'Requires the real local stack and a ChatGPT plan sign-in.',
)

for (const profile of ['local', 'cloud'] as const) {
  test(`live acceptance with the ${profile} execution profile`, async ({ page, request }) => {
    test.setTimeout(1_800_000)
    await page.addInitScript(() => {
      localStorage.setItem(
        'probeloop.preferences',
        JSON.stringify({ language: 'en', theme: 'light' }),
      )
    })
    await page.goto('/new-interview')
    const processing = page.getByRole('radio', {
      name: profile === 'local' ? 'On this computer' : 'ChatGPT plan',
      exact: true,
    })
    await expect(processing).toBeEnabled()
    await processing.click()
    await page.getByRole('radio', { name: 'Italian', exact: true }).click()
    await page.getByRole('radio', { name: 'HR screening', exact: true }).click()
    const next = page.getByTestId('step-continue')
    await next.click()
    await page.getByRole('radio', { name: 'This interview only', exact: true }).click()
    await next.click()
    const fixtures = '../../backend/tests/fixtures/synthetic/context/'
    await page
      .locator('#documents-cv-file')
      .setInputFiles(fileURLToPath(new URL(`${fixtures}synthetic-cv.pdf`, import.meta.url)))
    await expect(page.getByRole('textbox', { name: 'CV text', exact: true })).toHaveValue(
      /Giulia Neri/,
    )
    await page.getByRole('radio', { name: 'A real job offer', exact: true }).click()
    await page
      .locator('#documents-offer-file')
      .setInputFiles(fileURLToPath(new URL(`${fixtures}synthetic-offer.docx`, import.meta.url)))
    await expect(page.getByRole('textbox', { name: 'Job offer text', exact: true })).toHaveValue(
      /PagaFacile/,
    )
    await next.click()
    await expect(page.getByTestId('context-review')).toBeVisible({ timeout: 600_000 })
    // Inferred interpretations are excluded; the retained declared quotations are checked by code.
    const inferred = page
      .getByTestId('doubtful-facts')
      .getByTestId('context-fact')
      .filter({ hasText: 'Inferred: no quote found' })
    for (const fact of await inferred.all()) {
      await fact.getByRole('button', { name: 'Exclude', exact: true }).click()
      await expect(fact.getByRole('button', { name: 'Exclude', exact: true })).toHaveAttribute(
        'aria-pressed',
        'true',
      )
    }
    await next.click()
    await expect(page).toHaveURL(/\/final-check$/)
    const draft = await page.evaluate(
      () =>
        JSON.parse(sessionStorage.getItem('probeloop.prepare-draft') ?? '{}') as {
          state?: { snapshotId?: string }
        },
    )
    const snapshotId = draft.state?.snapshotId ?? ''
    expect(snapshotId).not.toBe('')
    const previous = (await (
      await request.get(`/api/snapshots/${snapshotId}/cv-reviews`)
    ).json()) as unknown[]
    const check = page.getByTestId('cv-check')
    await check.getByRole('button', { name: /^Check (the CV|again)$/ }).click()
    await expect(check.getByTestId('cv-score')).toContainText(
      `version ${String(previous.length + 1)}`,
      { timeout: 900_000 },
    )
    await check.getByRole('link', { name: 'Open the full CV report' }).click()
    await expect(page.getByTitle('Original CV')).toBeVisible()
    await page.screenshot({ path: `test-results/live-${profile}-cv-report.png` })
    const cvReportId = page.url().split('/').at(-1) ?? ''
    const cvReport = (await (await request.get(`/api/reports/${cvReportId}`)).json()) as {
      model_ref: string
      language: string
    }
    expect(cvReport.model_ref).toContain(profile === 'local' ? 'ollama:' : 'chatgpt:')
    expect(cvReport.language).toBe('it')
    await page.goBack()
    await page.getByTestId('enable-microphone').click()
    await expect(page.getByText('Say something')).toBeVisible()
    await next.click()
    await expect(page.getByTestId('answer')).toBeEnabled({ timeout: 600_000 })
    await page.getByTestId('answer').click()
    await page.waitForTimeout(12_000) // Stream a fixed amount of synthetic speech in real time.
    await page.getByTestId('end-answer').click()
    await expect(page.getByTestId('answer')).toBeEnabled({ timeout: 600_000 })
    await page.getByTestId('end-call').click()
    await expect(page.getByText('The interview has ended')).toBeVisible({ timeout: 60_000 })
    await page.getByTestId('review-transcript').click()
    await expect(page.getByTestId('refine-done')).toBeVisible({ timeout: 600_000 })
    await expect(page.getByTestId('answer-text')).not.toContainText('Segmento di prova')
    await page.screenshot({ path: `test-results/live-${profile}-transcript.png` })
    const sessionId = page.url().split('/').at(-1) ?? ''
    const session = (await (await request.get(`/api/sessions/${sessionId}`)).json()) as {
      execution_profile: string
    }
    expect(session.execution_profile).toBe(profile)
    await page.getByRole('button', { name: 'Generate report' }).click()
    const reportLink = page
      .getByTestId('interview-report-panel')
      .getByRole('link', { name: /^Open report v1 / })
    await expect(reportLink).toBeVisible({ timeout: 900_000 })
    await reportLink.click()
    await expect(page.getByRole('heading', { name: 'Question by question' })).toBeVisible()
    await page.screenshot({ path: `test-results/live-${profile}-interview-report.png` })
    const reportId = page.url().split('/').at(-1) ?? ''
    const report = (await (await request.get(`/api/reports/${reportId}`)).json()) as {
      model_ref: string
    }
    expect(report.model_ref).toContain(profile === 'local' ? 'ollama:' : 'chatgpt:')
    for (const format of ['md', 'json', 'pdf']) {
      expect((await request.get(`/api/reports/${reportId}/export/${format}`)).ok()).toBe(true)
    }
  })
}
