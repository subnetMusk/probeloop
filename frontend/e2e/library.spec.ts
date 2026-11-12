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
  const confirm = page.getByRole('button', { name: 'Confirm role and level', exact: true })
  await expect(confirm).toBeVisible({ timeout: 30_000 })
  await noSeriousViolations(page)
  await confirm.click()
  await page.getByRole('button', { name: 'Approve and check the CV', exact: true }).click()
  await expect(page).toHaveURL(/\/cv-checks\/\w+$/)
  await expect(page.getByTestId('cv-score')).toContainText('version 1', { timeout: 30_000 })
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

  await page.getByRole('link', { name: 'Check the CV', exact: true }).click()
  await expect(page).toHaveTitle('New CV check | ProbeLoop')
  await expect(page.getByRole('radio', { name, exact: true })).toBeChecked()
  await noSeriousViolations(page)
  await page.getByRole('button', { name: 'Analyse the documents', exact: true }).click()
  await approveAndCheck(page)
  await expect(page.getByRole('link', { name, exact: true })).toBeVisible()
  const checkUrl = page.url()

  await page.getByRole('link', { name, exact: true }).click()
  await expect(page.getByTestId('cv-check-row')).toHaveCount(1)

  // Deleting the profile keeps its CV check.
  await page.getByRole('button', { name: `Delete ${name}`, exact: true }).click()
  await page.getByRole('button', { name: 'Delete profile', exact: true }).click()
  await expect(page).toHaveURL(/\/profiles$/)
  await page.goto(checkUrl)
  await expect(page.getByTestId('cv-score')).toContainText('version 1')
  await page.goto('/cv-checks')
  await expect(
    page.getByTestId('cv-check-row').filter({ hasText: 'Profile: deleted profile' }).first(),
  ).toBeVisible()
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
