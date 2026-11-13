import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'
import type { Page } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

// The backend runs with scripted models (compose.test.yaml): the analysis turns every line of a
// document into a fact and adds one inferred fact, "Unverified model interpretation.".
const cvPath = fileURLToPath(
  new URL('../../backend/evals/fixtures/synthetic/context/backend-it.txt', import.meta.url),
)
const cv = readFileSync(cvPath, 'utf8')

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('probeloop.preferences', JSON.stringify({ language: 'en' }))
  })
})

const continueButton = (page: Page) => page.getByTestId('step-continue')

async function noSeriousViolations(page: Page) {
  const scan = await new AxeBuilder({ page }).analyze()
  expect(scan.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical')).toEqual(
    [],
  )
}

/** A new draft: the preparation keeps its data in the tab until the interview starts. */
async function startOver(page: Page) {
  await page.goto('/settings')
  await page.evaluate(() => {
    sessionStorage.clear()
  })
  await page.goto('/new-interview')
  await expect(page).toHaveURL(/\/new-interview\/interview-settings$/)
}

async function toDocuments(page: Page, profile: string) {
  await continueButton(page).click()
  await page.getByRole('radio', { name: profile, exact: true }).click()
  await continueButton(page).click()
  await expect(page).toHaveURL(/\/new-interview\/documents$/)
}

test('back and forward keep what was entered until the interview starts', async ({ page }) => {
  await startOver(page)
  await expect(page).toHaveTitle('Interview settings | ProbeLoop')
  const trail = page.getByRole('navigation', { name: 'Breadcrumbs' })
  await expect(trail).toContainText('New interview')
  await expect(page.getByText('Fields marked * are required.')).toBeVisible()
  await noSeriousViolations(page)
  await page.getByRole('radio', { name: 'HR screening', exact: true }).click()
  await page.getByRole('radio', { name: 'Hard', exact: true }).click()

  // A later step cannot open before the earlier ones are complete.
  await page.goto('/new-interview/documents')
  await expect(page).toHaveURL(/\/new-interview\/interview-settings$/)
  await expect(page.getByRole('radio', { name: 'HR screening', exact: true })).toBeChecked()
  await continueButton(page).click()

  await expect(page).toHaveURL(/\/new-interview\/resource-profile$/)
  await expect(continueButton(page)).toBeDisabled()
  await expect(page.getByText('Choose an option to continue.')).toBeVisible()
  await page.getByRole('radio', { name: 'This interview only', exact: true }).click()
  await noSeriousViolations(page)
  await continueButton(page).click()

  await expect(page).toHaveURL(/\/new-interview\/documents$/)
  await expect(continueButton(page)).toBeDisabled()
  await expect(page.getByText(/add your CV/)).toBeVisible()
  await page.getByRole('textbox', { name: 'CV text', exact: true }).fill(cv)
  await page.getByRole('button', { name: 'Add a resource' }).click()
  const resource = page.getByTestId('resource-row').first()
  await resource.getByRole('textbox', { name: 'Title', exact: true }).fill('Routing notes')
  await expect(continueButton(page)).toBeDisabled()
  await resource
    .getByRole('textbox', { name: 'Resource text', exact: true })
    .fill('A routing service in Go.')
  await noSeriousViolations(page)

  // Back and forward through the steps, and a reload, keep the documents.
  await page.getByRole('button', { name: 'Back', exact: true }).click()
  await expect(page.getByRole('radio', { name: 'This interview only', exact: true })).toBeChecked()
  await page.goBack()
  await expect(page).toHaveURL(/\/new-interview\/documents$/)
  await page.reload()
  await expect(page.getByRole('textbox', { name: 'CV text', exact: true })).toHaveValue(cv)
  await expect(resource.getByRole('textbox', { name: 'Title', exact: true })).toHaveValue(
    'Routing notes',
  )
  await continueButton(page).click()

  await expect(page).toHaveURL(/\/new-interview\/fact-review$/)
  await expect(page.getByTestId('context-review')).toBeVisible({ timeout: 30_000 })
  await expect(continueButton(page)).toBeDisabled()
  await expect(
    page.getByText('Confirm the target profession, role and level to continue.'),
  ).toBeVisible()
  const doubtful = page.getByTestId('doubtful-facts').getByTestId('context-fact').first()
  await expect(doubtful).toContainText('Unverified model interpretation.')
  await doubtful.getByRole('button', { name: 'Exclude', exact: true }).click()
  await expect(doubtful.getByRole('button', { name: 'Exclude', exact: true })).toHaveAttribute(
    'aria-pressed',
    'true',
  )
  await page
    .getByRole('textbox', { name: 'Target level or training grade', exact: true })
    .fill('Junior under supervision')
  await page.getByRole('button', { name: 'Back', exact: true }).click()
  await continueButton(page).click()
  await expect(
    page.getByRole('textbox', { name: 'Target level or training grade', exact: true }),
  ).toHaveValue('Junior under supervision')
  await noSeriousViolations(page)
  // Approving confirms the role as shown.
  await continueButton(page).click()

  await expect(page).toHaveURL(/\/new-interview\/final-check$/)
  await expect(page.getByTestId('cv-check')).toBeVisible()
  await noSeriousViolations(page)

  // Back to the review after approval: a change reopens it, and approving again continues.
  await page.getByRole('button', { name: 'Back', exact: true }).click()
  await expect(page).toHaveURL(/\/new-interview\/fact-review$/)
  await doubtful.getByRole('button', { name: 'Exclude', exact: true }).click()
  await expect(doubtful.getByRole('button', { name: 'Exclude', exact: true })).toHaveAttribute(
    'aria-pressed',
    'false',
  )
  await page.goto('/new-interview/final-check')
  await expect(page).toHaveURL(/\/new-interview\/fact-review$/)
  await continueButton(page).click()
  await expect(page).toHaveURL(/\/new-interview\/final-check$/)

  // The settings are still those chosen at the start.
  await page.getByRole('link', { name: 'Change: Type' }).click()
  await expect(page.getByRole('radio', { name: 'HR screening', exact: true })).toBeChecked()
  await expect(page.getByRole('radio', { name: 'Hard', exact: true })).toBeChecked()
})

test('an uploaded CV and a drafted job offer reach the CV check', async ({ page, request }) => {
  await startOver(page)
  await toDocuments(page, 'This interview only')
  await page.locator('#documents-cv-file').setInputFiles(cvPath)
  await expect(page.getByRole('link', { name: 'Original file' })).toBeVisible({ timeout: 30_000 })
  await expect(page.getByRole('textbox', { name: 'CV text', exact: true })).toHaveValue(/\S/)
  await page.getByRole('radio', { name: 'Describe a role', exact: true }).click()
  await page
    .getByLabel('Role description', { exact: true })
    .fill('Backend engineer working on Python and PostgreSQL services.')
  await page.getByRole('button', { name: 'Draft the job offer', exact: true }).click()
  const offer = page.getByRole('textbox', { name: 'Job offer text', exact: true })
  await expect(offer).toContainText('Backend engineer')
  await offer.fill(`${await offer.inputValue()}\nFastAPI experience is preferred.`)
  await continueButton(page).click()

  await expect(page.getByTestId('context-review')).toBeVisible({ timeout: 30_000 })
  await expect(page.getByText('The job offer was drafted from your description.')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Job requirements', exact: true })).toBeVisible()
  await expect(page.getByTestId('requirements').getByRole('listitem').first()).toBeVisible()
  const doubtful = page.getByTestId('doubtful-facts').getByTestId('context-fact').first()
  await doubtful.getByRole('button', { name: 'Correct', exact: true }).click()
  await doubtful.getByLabel('Corrected statement').fill('Uses FastAPI for internal services.')
  await doubtful.getByRole('button', { name: 'Save correction', exact: true }).click()
  await expect(doubtful).toContainText('Uses FastAPI for internal services.')
  await page.locator('summary', { hasText: 'Add a fact the documents miss' }).click()
  await page.getByLabel('Fact', { exact: true }).fill('Uses Go for personal projects.')
  await page.getByRole('button', { name: 'Add fact', exact: true }).click()
  await page.locator('summary', { hasText: 'All facts' }).click()
  await expect(
    page.getByTestId('context-fact').filter({ hasText: 'Uses Go for personal projects.' }),
  ).toContainText('Added by you')
  await page.reload()
  await expect(page.getByTestId('context-review')).toBeVisible()
  await continueButton(page).click()

  const check = page.getByTestId('cv-check')
  // The same documents give the same approved context, so earlier runs may have left versions.
  const snapshotId = await page.evaluate(() => {
    const stored = JSON.parse(sessionStorage.getItem('probeloop.prepare-draft') ?? '{}') as {
      state?: { snapshotId?: string }
    }
    return stored.state?.snapshotId ?? ''
  })
  const reviews = await request.get(`/api/snapshots/${snapshotId}/cv-reviews`)
  const before = ((await reviews.json()) as unknown[]).length
  const run = check.getByRole('button', { name: /^Check (the CV|again)$/ })
  const score = check.getByTestId('cv-score')
  for (const version of [before + 1, before + 2]) {
    await run.click()
    await expect(score).toContainText(`version ${String(version)}`, { timeout: 30_000 })
  }
  // The full report opens in a new tab, so the preparation stays where it is.
  const [report] = await Promise.all([
    page.waitForEvent('popup'),
    check.getByRole('link', { name: /^Open the full CV report/ }).click(),
  ])
  await expect(report).toHaveURL(/\/cv-checks\/\w+\/reports\/\w+$/)
  await expect(report.getByText('Synthetic assessment.', { exact: true }).first()).toBeVisible()
  await report.close()
  await expect(page).toHaveURL(/\/new-interview\/final-check$/)
})

test('a quick start requires an explicit role and level without demo facts', async ({
  page,
  request,
}) => {
  await startOver(page)
  // The test backend has an interviewer voice for Italian only.
  await expect(page.getByRole('radio', { name: 'English', exact: true })).toBeDisabled()
  await expect(page.getByRole('radio', { name: 'Italian', exact: true })).toBeChecked()
  await continueButton(page).click()
  await page.getByRole('radio', { name: 'No documents', exact: true }).click()
  await continueButton(page).click()
  await expect(page).toHaveURL(/\/new-interview\/fact-review$/)
  await expect(continueButton(page)).toBeDisabled()
  await page.getByRole('textbox', { name: 'Profession or field', exact: true }).fill('Economics')
  await page.getByRole('textbox', { name: 'Target role', exact: true }).fill('Research economist')
  await page
    .getByRole('textbox', { name: 'Target level or training grade', exact: true })
    .fill('Junior under supervision')
  await continueButton(page).click()
  await expect(page).toHaveURL(/\/new-interview\/final-check$/)
  const snapshotId = await page.evaluate(
    () =>
      (
        JSON.parse(sessionStorage.getItem('probeloop.prepare-draft') ?? '{}') as {
          state: { snapshotId: string }
        }
      ).state.snapshotId,
  )
  const snapshot = (await (await request.get(`/api/snapshots/${snapshotId}`)).json()) as {
    candidate_brief: string
    role_profile: { target_role: string }
  }
  expect(snapshot.candidate_brief).not.toContain('Marco')
  expect(snapshot.role_profile.target_role).toBe('Research economist')
  await expect(page.getByTestId('cv-check')).toHaveCount(0)
  await expect(page.getByRole('navigation', { name: 'Preparation steps' })).toContainText('skipped')
  await expect(continueButton(page)).toBeDisabled()
  await page.getByTestId('enable-microphone').click()
  await expect(page.getByText('Say something')).toBeVisible()
  await expect(continueButton(page)).toBeEnabled()
  await page.getByRole('button', { name: 'Back', exact: true }).click()
  await expect(page).toHaveURL(/\/new-interview\/fact-review$/)
})

test('a changed profile can be overwritten, copied or used once', async ({ page, request }) => {
  const name = `Synthetic profile ${String(Date.now())}`
  await startOver(page)
  await continueButton(page).click()
  await page.getByRole('radio', { name: 'New profile', exact: true }).click()
  await expect(continueButton(page)).toBeDisabled()
  await page.getByRole('textbox', { name: 'Profile name', exact: true }).fill(name)
  await continueButton(page).click()
  await page.getByRole('textbox', { name: 'CV text', exact: true }).fill(cv)
  await page.getByRole('button', { name: 'Add a resource' }).click()
  const row = page.getByTestId('resource-row').first()
  await row.getByRole('textbox', { name: 'Title', exact: true }).fill('Routing notes')
  await row
    .getByRole('textbox', { name: 'Resource text', exact: true })
    .fill('A routing service in Go.')
  await continueButton(page).click()
  await expect(page.getByTestId('context-review')).toBeVisible({ timeout: 30_000 })

  const edit = async (title: string) => {
    await startOver(page)
    await toDocuments(page, name)
    await expect(row.getByRole('textbox', { name: 'Title', exact: true })).not.toHaveValue('')
    await expect(page.getByRole('textbox', { name: 'CV text', exact: true })).toHaveValue(cv.trim())
    await row.getByRole('textbox', { name: 'Title', exact: true }).fill(title)
    await continueButton(page).click()
    await expect(page.getByRole('dialog')).toContainText('Keep these changes in the profile?')
  }
  await edit('Copied routing notes')
  await page.getByRole('radio', { name: 'Save as a new profile' }).click()
  await page
    .getByRole('textbox', { name: 'Name of the new profile', exact: true })
    .fill(`${name} copy`)
  await page.getByRole('button', { name: 'Continue', exact: true }).last().click()
  await expect(page.getByTestId('context-review')).toBeVisible({ timeout: 30_000 })

  await edit('Updated routing notes')
  await page.getByRole('radio', { name: `Overwrite “${name}”` }).click()
  await page.getByRole('button', { name: 'Continue', exact: true }).last().click()
  await expect(page.getByTestId('context-review')).toBeVisible({ timeout: 30_000 })

  await edit('Interview-only notes')
  await page.getByRole('radio', { name: 'Use them for this interview only' }).click()
  await page.getByRole('button', { name: 'Continue', exact: true }).last().click()
  await expect(page.getByTestId('context-review')).toBeVisible({ timeout: 30_000 })

  const profiles = (await (await request.get('/api/profiles')).json()) as {
    id: string
    name: string
    cv: { id: string } | null
    resources: { title: string }[]
  }[]
  const original = profiles.find((p) => p.name === name)
  expect(original?.cv).not.toBeNull()
  expect(original?.resources.map((r) => r.title)).toEqual(['Updated routing notes'])
  const copy = profiles.find((p) => p.name === `${name} copy`)
  expect(copy?.resources.map((r) => r.title)).toEqual(['Copied routing notes'])
  for (const profile of [original, copy]) {
    if (profile) await request.delete(`/api/profiles/${profile.id}`)
  }
})
