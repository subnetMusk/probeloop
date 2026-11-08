import { expect, test } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const cvPath = fileURLToPath(
  new URL('../../backend/evals/fixtures/synthetic/context/backend-it.txt', import.meta.url),
)
const cv = readFileSync(cvPath, 'utf8')
test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('probeloop.preferences', JSON.stringify({ language: 'en' }))
  })
})

test('quick start keeps the microphone setup available', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Quick start without documents' }).click()
  await expect(page.getByTestId('enable-microphone')).toBeVisible()
  await expect(page.getByTestId('start-interview')).toBeDisabled()
})

test('an uploaded CV and an edited generated offer reach approval', async ({ page }, testInfo) => {
  await page.goto('/')
  await page.getByLabel('Or upload a text document').setInputFiles(cvPath)
  await page.getByRole('combobox', { name: 'Job offer source' }).click()
  await page.getByRole('option', { name: 'Describe a role', exact: true }).click()
  await page
    .getByLabel('Describe the role', { exact: true })
    .fill('Backend engineer working on Python and PostgreSQL services.')
  await page.getByRole('button', { name: 'Draft a job offer', exact: true }).click()
  const generated = page.getByLabel('Generated offer', { exact: true })
  await expect(generated).toContainText('Backend engineer')
  await generated.fill(`${await generated.inputValue()}\nFastAPI experience is preferred.`)
  await page.getByRole('button', { name: 'Continue to resources' }).click()
  await page.getByRole('button', { name: 'Analyse documents', exact: true }).click()
  await expect(page.getByTestId('context-review')).toBeVisible({ timeout: 30_000 })
  await expect(
    page.getByText('Job offer drafted from your description', { exact: true }),
  ).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Requirement matrix', exact: true })).toBeVisible()
  const fact = page.getByTestId('context-fact').first()
  await fact.getByRole('button', { name: 'Correct', exact: true }).click()
  await fact.getByLabel('Corrected fact').fill('Synthetic candidate with backend experience.')
  await fact.getByRole('button', { name: 'Save correction', exact: true }).click()
  await expect(fact).toContainText('corrected')
  await page.getByLabel('New fact', { exact: true }).fill('Uses Go for personal projects.')
  await page.getByRole('button', { name: 'Add fact', exact: true }).click()
  await expect(
    page.getByTestId('context-fact').filter({ hasText: 'Uses Go for personal projects.' }),
  ).toContainText('Added')
  await page.reload()
  await expect(page.getByTestId('context-review')).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath('context-review.png'), fullPage: true })
  await page.getByRole('button', { name: 'Approve context and continue' }).click()
  await expect(page.getByTestId('enable-microphone')).toBeVisible()
  const review = page.getByTestId('cv-review-panel')
  await review.getByRole('combobox', { name: 'Report language', exact: true }).click()
  await page.getByRole('option', { name: 'Italiano', exact: true }).click()
  await review.getByRole('button', { name: 'Genera revisione CV' }).click()
  const first = review.getByRole('link', { name: /Apri revisione v1/ })
  await expect(first).toBeVisible({ timeout: 30_000 })
  await review.getByRole('button', { name: 'Genera revisione CV' }).click()
  await expect(review.getByRole('link', { name: /Apri revisione v2/ })).toBeVisible()
  await first.click()
  await expect(page.getByRole('heading', { name: 'Revisione del CV', exact: true })).toBeVisible()
  await expect(page.getByText('Synthetic assessment.', { exact: true }).first()).toBeVisible()
})

test('resource profiles can be created, overwritten, copied or used once', async ({
  page,
  request,
}) => {
  const name = `Synthetic profile ${Date.now()}`
  const begin = async () => {
    await page.goto('/')
    await page.evaluate(() => {
      sessionStorage.clear()
    })
    await page.reload()
    await page.getByLabel('CV text', { exact: true }).fill(cv)
    await page.getByRole('button', { name: 'Continue to resources' }).click()
  }
  await begin()
  const row = page.getByTestId('resource-row').first()
  await row.getByLabel('Title', { exact: true }).fill('Routing notes')
  await row.getByLabel('Resource text', { exact: true }).fill(cv)
  await expect(page.getByTestId('resource-row')).toHaveCount(2)
  await page.getByRole('button', { name: 'Analyse documents', exact: true }).click()
  await page.getByLabel('Save as a new profile', { exact: true }).check()
  await page.getByLabel('Profile name', { exact: true }).fill(name)
  await page.getByRole('button', { name: 'Continue with analysis', exact: true }).click()
  await expect(page.getByTestId('context-review')).toBeVisible({ timeout: 30_000 })

  await begin()
  await page.getByRole('combobox', { name: 'Resource profile' }).click()
  await page.getByRole('option', { name, exact: true }).click()
  await expect(row.getByLabel('Title', { exact: true })).toHaveValue('Routing notes')
  await row.getByLabel('Title', { exact: true }).fill('Copied routing notes')
  await page.getByRole('button', { name: 'Analyse documents', exact: true }).click()
  await page.getByLabel('Save as a new profile', { exact: true }).check()
  await page.getByLabel('Profile name', { exact: true }).fill(`${name} copy`)
  await page.getByRole('button', { name: 'Continue with analysis', exact: true }).click()
  await expect(page.getByTestId('context-review')).toBeVisible({ timeout: 30_000 })

  await begin()
  await page.getByRole('combobox', { name: 'Resource profile' }).click()
  await page.getByRole('option', { name, exact: true }).click()
  await expect(row.getByLabel('Resource text', { exact: true })).toHaveValue(cv.trim())
  await row.getByLabel('Title', { exact: true }).fill('Updated routing notes')
  await page.getByRole('button', { name: 'Analyse documents', exact: true }).click()
  await page.getByLabel(`Overwrite ${name}`, { exact: true }).check()
  await page.getByRole('button', { name: 'Continue with analysis', exact: true }).click()
  await expect(page.getByTestId('context-review')).toBeVisible({ timeout: 30_000 })

  await begin()
  await page.getByRole('combobox', { name: 'Resource profile' }).click()
  await page.getByRole('option', { name, exact: true }).click()
  await expect(row.getByLabel('Title', { exact: true })).toHaveValue('Updated routing notes')
  await row.getByLabel('Title', { exact: true }).fill('Interview-only notes')
  await page.getByRole('button', { name: 'Analyse documents', exact: true }).click()
  await page.getByLabel('Use for this interview only', { exact: true }).check()
  await page.getByRole('button', { name: 'Continue with analysis', exact: true }).click()
  await expect(page.getByTestId('context-review')).toBeVisible({ timeout: 30_000 })

  const profiles = (await (await request.get('/api/profiles')).json()) as {
    id: string
    name: string
    resources: { title: string }[]
  }[]
  const original = profiles.find((p) => p.name === name)
  expect(original?.resources[0]?.title).toBe('Updated routing notes')
  const copy = profiles.find((p) => p.name === `${name} copy`)
  expect(copy?.resources[0]?.title).toBe('Copied routing notes')
  for (const profile of [original, copy]) {
    if (profile) await request.delete(`/api/profiles/${profile.id}`)
  }
})
