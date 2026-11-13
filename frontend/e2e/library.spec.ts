import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'
import type { Page } from '@playwright/test'
import { readFileSync } from 'node:fs'

// The backend runs with scripted models (compose.test.yaml). Profiles and CV checks are created
// without preparing an interview. Each run adds a unique line to the CV, so that its approved
// context is new and earlier runs leave no versions behind.
const cv = readFileSync(
  new URL('../../backend/evals/fixtures/synthetic/context/backend-it.txt', import.meta.url),
  'utf8',
)

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('probeloop.preferences', JSON.stringify({ language: 'en' }))
  })
})

async function noSeriousViolations(page: Page) {
  const scan = await new AxeBuilder({ page }).analyze()
  expect(scan.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical')).toEqual(
    [],
  )
}

/** From the review of the analysis to the first version of the CV check. */
async function approveAndCheck(page: Page) {
  await expect(page).toHaveURL(/\/cv-checks\/new\/\w+$/)
  await expect(page).toHaveTitle('Review | ProbeLoop')
  // Approving confirms the target role as shown.
  await expect(page.getByTestId('role-profile')).toBeVisible({ timeout: 30_000 })
  await noSeriousViolations(page)
  await page.getByRole('button', { name: 'Approve and check the CV', exact: true }).click()
  await expect(page).toHaveURL(/\/cv-checks\/\w+$/)
  // The check's page shows the report itself, with its version.
  await expect(page.getByRole('combobox', { name: 'Version' })).toContainText('Version 1', {
    timeout: 30_000,
  })
  await expect(page.getByTestId('report-content')).toBeVisible()
}

test('a profile is created on its own and its CV checked without an interview', async ({
  page,
}) => {
  const name = `Library profile ${String(Date.now())}`
  await page.goto('/profiles')
  await page.getByRole('link', { name: 'New profile', exact: true }).click()
  await expect(page).toHaveTitle('New profile | ProbeLoop')
  await page.getByRole('textbox', { name: 'Profile name', exact: true }).fill(name)
  await page
    .getByRole('textbox', { name: 'CV text', exact: true })
    .fill(`${cv.trim()}\nRun ${name}.`)
  await noSeriousViolations(page)
  await page.getByRole('button', { name: 'Save the profile', exact: true }).click()
  await expect(page).toHaveTitle('Profile | ProbeLoop')
  await expect(page.getByRole('heading', { level: 1 })).toContainText(name)

  // Checking a profile's CV analyses its documents at once and opens the review.
  await page.getByRole('button', { name: 'Check the CV', exact: true }).click()
  await approveAndCheck(page)
  await expect(page.getByRole('link', { name, exact: true })).toBeVisible()
  const checkUrl = page.url()

  // The approved context starts an interview that goes from the settings to the final check.
  await page
    .getByRole('button', { name: 'Practise an interview on this context', exact: true })
    .click()
  await expect(page).toHaveURL(/\/new-interview\/interview-settings$/)
  await page.getByTestId('step-continue').click()
  await expect(page).toHaveURL(/\/new-interview\/final-check$/)
  await expect(page.getByText(/^Approved in the CV check of /)).toBeVisible()
  await page.goto(checkUrl)

  await page.getByRole('link', { name, exact: true }).click()
  await expect(page.getByTestId('cv-check-row')).toHaveCount(1)

  // Deleting the profile keeps its CV check.
  await page.getByRole('button', { name: `Delete ${name}`, exact: true }).click()
  await page.getByRole('button', { name: 'Delete profile', exact: true }).click()
  await expect(page).toHaveURL(/\/profiles$/)
  await page.goto(checkUrl)
  await expect(page.getByRole('combobox', { name: 'Version' })).toContainText('Version 1')
  await page.goto('/cv-checks')
  await expect(
    page.getByTestId('cv-check-row').filter({ hasText: 'Profile: deleted profile' }).first(),
  ).toBeVisible()
})

test('an unfinished CV check stays reachable after leaving its page', async ({ page, request }) => {
  const name = `Unfinished ${String(Date.now())}`
  const typed = await request.post('/api/documents/text', {
    data: { kind: 'cv', title: 'CV', text: `${cv.trim()}\nRun ${name}.` },
  })
  const document = (await typed.json()) as { id: string }
  const saved = await request.post('/api/profiles', {
    data: { name, cv_id: document.id, job_offer_id: null, resources: [] },
  })
  expect(saved.ok()).toBe(true)
  const profile = (await saved.json()) as { id: string }
  const main = page.getByRole('navigation', { name: 'Main' })

  await page.goto(`/cv-checks/new?profile=${profile.id}`)
  await expect(page.getByRole('radio', { name, exact: true })).toBeChecked()
  // The profile's documents can be corrected here before the analysis.
  const cvText = page.getByRole('textbox', { name: 'CV text', exact: true })
  await expect(cvText).toHaveValue(new RegExp(`Run ${name}`))
  await noSeriousViolations(page)
  await page.getByRole('button', { name: 'Analyse the documents', exact: true }).click()
  await expect(page).toHaveURL(/\/cv-checks\/new\/\w+$/)
  await expect(page.getByTestId('role-profile')).toBeVisible({ timeout: 30_000 })

  // Going back refills the form with the same documents; analysing again replaces the check.
  await page.getByRole('link', { name: 'Back to the documents', exact: true }).click()
  await expect(page).toHaveURL(/\/cv-checks\/new\?from=\w+$/)
  await expect(page.getByRole('radio', { name, exact: true })).toBeChecked()
  await expect(cvText).toHaveValue(new RegExp(`Run ${name}`))
  await page.getByRole('button', { name: 'Analyse the documents', exact: true }).click()
  await expect(page).toHaveURL(/\/cv-checks\/new\/\w+$/)
  const reviewUrl = page.url()
  await expect(page.getByTestId('role-profile')).toBeVisible({ timeout: 30_000 })

  // Elsewhere, then back through the navigation: the analysis waits under CV checks.
  await main.getByRole('link', { name: 'Interviews', exact: true }).click()
  await expect(page).toHaveURL(/\/interviews$/)
  await main.getByRole('link', { name: 'CV checks', exact: true }).click()
  const unfinished = page.getByTestId('unfinished-cv-check')
  await expect(unfinished).toHaveCount(1)
  await expect(unfinished).toContainText('Analysis ready to review')
  await noSeriousViolations(page)
  await page.getByRole('link', { name: 'New CV check', exact: true }).click()
  await expect(page.getByText('A CV check you started is not finished.')).toBeVisible()
  // The notice opens the unfinished check directly.
  await unfinished.getByRole('link').click()
  await expect(page).toHaveURL(reviewUrl)

  await approveAndCheck(page)
  await page.goto('/cv-checks')
  await expect(page.getByTestId('cv-check-row').first()).toBeVisible()
  await expect(unfinished).toHaveCount(0)
  await request.delete(`/api/profiles/${profile.id}`)
})

test('a one-off CV check is saved as a profile, then deleted', async ({ page, request }) => {
  const name = `From a check ${String(Date.now())}`
  await page.goto('/cv-checks')
  await page.getByRole('link', { name: 'New CV check', exact: true }).click()
  await page.getByRole('radio', { name: 'Documents for this check', exact: true }).click()
  await page
    .getByRole('textbox', { name: 'CV text', exact: true })
    .fill(`${cv.trim()}\nRun ${name}.`)
  await page.getByRole('button', { name: 'Analyse the documents', exact: true }).click()
  await approveAndCheck(page)
  const snapshotId = page.url().split('/').at(-1) ?? ''

  await page.getByRole('button', { name: 'Save as a profile', exact: true }).click()
  await page.getByRole('textbox', { name: 'Profile name', exact: true }).fill(name)
  await page.getByRole('button', { name: 'Save the profile', exact: true }).click()
  await expect(page.getByRole('link', { name, exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Save as a profile', exact: true })).toHaveCount(0)

  await page.getByRole('button', { name: 'Delete', exact: true }).click()
  await page.getByRole('button', { name: 'Delete CV check', exact: true }).click()
  await expect(page).toHaveURL(/\/cv-checks$/)
  expect((await request.get(`/api/snapshots/${snapshotId}`)).status()).toBe(404)
  // The profile keeps the documents, so the check can run again from it.
  const profiles = (await (await request.get('/api/profiles')).json()) as {
    id: string
    name: string
    cv: { id: string } | null
  }[]
  const profile = profiles.find((p) => p.name === name)
  expect(profile?.cv).not.toBeNull()
  expect((await request.get(`/api/documents/${profile?.cv?.id ?? ''}`)).status()).toBe(200)
  await request.delete(`/api/profiles/${profile?.id ?? ''}`)
})
