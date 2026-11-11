import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'
import type { APIRequestContext, Page } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { setTheme } from './helpers/theme.js'
import type { components } from '../src/shared/api/types/rest.js'

type RoleProfileData = components['schemas']['RoleProfileData']

// The backend runs with scripted models (compose.test.yaml). The history is seeded through the
// API, so these tests do not depend on what other specs left in the test volume.
const cv = readFileSync(
  new URL('../../backend/evals/fixtures/synthetic/context/backend-it.txt', import.meta.url),
  'utf8',
)

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('probeloop.preferences', JSON.stringify({ language: 'en' }))
  })
})

async function json<T>(response: Promise<{ json: () => Promise<unknown> }>): Promise<T> {
  return (await (await response).json()) as T
}

/** A CV check with one review: a typed CV, its analysis, approval and the review job. */
async function seedCvCheck(request: APIRequestContext): Promise<string> {
  const document = await json<{ id: string }>(
    request.post('/api/documents/text', { data: { kind: 'cv', title: 'CV', text: cv } }),
  )
  const preparation = await json<{ id: string }>(
    request.post('/api/preparations', { data: { job_mode: 'none', cv_id: document.id } }),
  )
  await expect
    .poll(
      async () =>
        (await json<{ status: string }>(request.get(`/api/preparations/${preparation.id}`))).status,
      { timeout: 30_000 },
    )
    .toBe('review')
  const reviewed = await json<{ role_profile: RoleProfileData }>(
    request.get(`/api/preparations/${preparation.id}`),
  )
  await request.put(`/api/preparations/${preparation.id}/role-profile`, {
    data: { ...reviewed.role_profile, confirmed: true },
  })
  const snapshot = await json<{ id: string }>(
    request.post(`/api/preparations/${preparation.id}/approve`),
  )
  const job = await json<{ id: string }>(
    request.post(`/api/snapshots/${snapshot.id}/cv-reviews`, { data: { language: 'en' } }),
  )
  await expect
    .poll(async () => (await json<{ status: string }>(request.get(`/api/jobs/${job.id}`))).status, {
      timeout: 30_000,
    })
    .toBe('succeeded')
  return snapshot.id
}

async function noSeriousViolations(page: Page) {
  const scan = await new AxeBuilder({ page }).analyze()
  expect(scan.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical')).toEqual(
    [],
  )
}

test('the dashboard summarises the history a short page at a time', async ({ page, request }) => {
  for (let i = 0; i < 6; i++) {
    const created = await request.post('/api/sessions', {
      data: { interview_type: 'hr', language: 'it', duration_minutes: 5 },
    })
    expect(created.ok()).toBe(true)
  }
  const snapshotId = await seedCvCheck(request)
  const interviews = await json<unknown[]>(request.get('/api/history/interviews'))

  await page.goto('/')
  await expect(page).toHaveTitle('Dashboard | ProbeLoop')
  const summary = page.getByRole('region', { name: 'Summary' })
  await expect(summary).toContainText('Interviews')
  await expect(summary).toContainText('CV checks')
  await expect(page.getByRole('heading', { name: 'CV check scores' })).toBeVisible()
  await expect(page.getByRole('img', { name: /Overall CV check scores over time/ })).toBeVisible()

  // Newest first, four at a time.
  const rows = page.getByTestId('interview-row')
  await expect(rows).toHaveCount(4)
  await expect(rows.first()).toContainText('HR screening')
  await expect(rows.first()).toContainText('Not started')
  const pager = page.getByRole('navigation', { name: 'Recent interviews' })
  await expect(pager).toContainText(`1 of ${String(Math.ceil(interviews.length / 4))}`)
  await pager.getByRole('button', { name: 'Next page' }).click()
  await expect(pager).toContainText('2 of')
  await expect(page.getByRole('link', { name: 'All interviews' })).toBeVisible()

  // The short dashboard scrolls inside the shell without the long-page control.
  const content = page.getByTestId('content')
  const top = page.getByRole('button', { name: 'Back to top' })
  await content.evaluate((element) => {
    element.scrollTo({ top: element.scrollHeight })
  })
  await expect(top).toBeHidden()
  await expect(page.getByRole('navigation', { name: 'Main' })).toBeInViewport()
  expect(await page.evaluate(() => window.scrollY)).toBe(0)
  await noSeriousViolations(page)

  // The CV checks are a short list too; each opens its own page.
  const checks = page.getByTestId('cv-check-row')
  await expect(checks.first()).toBeVisible()
  expect(await checks.count()).toBeLessThanOrEqual(4)
  await page.goto(`/cv-checks/${snapshotId}`)
  await expect(page).toHaveTitle('CV check | ProbeLoop')
  await expect(page.getByRole('heading', { name: 'Versions' })).toBeVisible()
  const versions = await json<{ version: number }[]>(
    request.get(`/api/snapshots/${snapshotId}/cv-reviews`),
  )
  const latestVersion = versions.at(-1)?.version ?? 1
  const latestReport = page.getByRole('link', {
    name: new RegExp(`^Version ${String(latestVersion)} ·`),
  })
  await expect(latestReport).toBeVisible()
  await expect(page.getByText('Typed text: there is no original file.')).toBeVisible()
  await noSeriousViolations(page)
  await latestReport.click()
  await expect(page).toHaveTitle('Report | ProbeLoop')
  await expect(page.getByRole('heading', { name: 'Document checks' })).toBeVisible()
  for (const theme of ['light', 'dark']) {
    await setTheme(page, theme)
    await noSeriousViolations(page)
  }
  await page.screenshot({ path: 'test-results/cv-report.png' })

  await page.goto('/interviews')
  await page
    .getByRole('group', { name: 'Status' })
    .getByRole('button', { name: 'Completed', exact: true })
    .click()
  await expect(page.getByTestId('interview-row').filter({ hasText: 'Not started' })).toHaveCount(0)
  await noSeriousViolations(page)
})

test('a profile is renamed in place, edited on its page and used', async ({ page, request }) => {
  const name = `Dashboard profile ${String(Date.now())}`
  const document = await json<{ id: string }>(
    request.post('/api/documents/text', { data: { kind: 'cv', title: 'CV', text: cv } }),
  )
  const profile = await json<{ id: string }>(
    request.post('/api/profiles', { data: { name, cv_id: document.id, resources: [] } }),
  )

  await page.goto('/profiles')
  await expect(page).toHaveTitle('Profiles | ProbeLoop')
  const row = page.getByTestId('profile-row').filter({ hasText: name })
  await row.getByRole('button', { name: `Rename ${name}` }).click()
  const field = page.getByRole('textbox', { name: 'Profile name' })
  await field.fill(`${name} renamed`)
  await field.press('Enter')
  await expect(page.getByText(`${name} renamed`, { exact: true })).toBeVisible()
  await noSeriousViolations(page)

  await page.getByRole('link', { name: `Open ${name} renamed` }).click()
  await expect(page).toHaveTitle('Profile | ProbeLoop')
  const text = page.getByRole('textbox', { name: 'CV text', exact: true })
  await expect(text).toHaveValue(cv.trim())
  await text.fill(`${cv.trim()}\nAlso maintains the CI pipeline.`)
  await expect(page.getByText('Unsaved changes')).toBeVisible()
  await page.getByRole('button', { name: 'Save changes' }).click()
  await expect(page.getByText('Unsaved changes')).toHaveCount(0)
  const saved = (
    await json<{ id: string; cv: { id: string } | null }[]>(request.get('/api/profiles'))
  ).find((p) => p.id === profile.id)
  expect(saved?.cv?.id).not.toBe(document.id)

  await page.getByRole('button', { name: 'New interview with this profile' }).click()
  await expect(page).toHaveURL(/\/new-interview\/interview-settings$/)
  await page.getByTestId('step-continue').click()
  await expect(page.getByRole('radio', { name: `${name} renamed`, exact: true })).toBeChecked()
  await request.delete(`/api/profiles/${profile.id}`)
})
