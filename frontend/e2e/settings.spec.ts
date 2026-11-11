import { expect, test } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import type { components } from '../src/shared/api/types/rest.ts'

type ExecutionView = components['schemas']['ExecutionView']

test('language, keyboard volume and system theme persist across reloads', async ({ page }) => {
  await page.goto('/settings')
  await page.getByRole('combobox', { name: 'Lingua', exact: true }).click()
  await page.getByRole('option', { name: 'English', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Settings', exact: true })).toBeVisible()
  const volume = page.getByRole('slider', { name: /Interviewer volume/ })
  await volume.focus()
  await volume.press('End')
  await volume.press('ArrowLeft')
  await expect(volume).toHaveValue('99')
  await page.getByRole('combobox', { name: 'Theme', exact: true }).click()
  await page.getByRole('option', { name: 'Dark', exact: true }).click()
  await page.reload()
  await expect(page.locator('html')).toHaveAttribute('lang', 'en')
  await expect(page.locator('html')).toHaveClass('dark')
  await expect(page.getByRole('slider')).toHaveValue('99')
  await page.getByRole('combobox', { name: 'Theme', exact: true }).click()
  await page.getByRole('option', { name: 'System', exact: true }).click()
  await page.emulateMedia({ colorScheme: 'light' })
  await expect(page.locator('html')).not.toHaveClass('dark')
  await page.emulateMedia({ colorScheme: 'dark' })
  await expect(page.locator('html')).toHaveClass('dark')
  const scan = await new AxeBuilder({ page }).analyze()
  expect(scan.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical')).toEqual(
    [],
  )
})

// The test backend scripts every model; its cloud profile reuses the scripted models, and its
// ChatGPT account signs in by returning straight to the callback.
test('tools are selected by role in Settings and shown on the dashboard', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('probeloop.preferences', JSON.stringify({ language: 'en' }))
  })
  const analysis = page.getByRole('combobox', { name: 'Document analysis', exact: true })
  const interviewer = page.getByRole('combobox', { name: 'Interviewer', exact: true })
  const limits = page.getByRole('combobox', { name: 'Stated limits', exact: true })
  const account = page.getByRole('region', { name: 'ChatGPT account' })
  const reset = await page.request.post('/api/settings/chatgpt/sign-out', { data: {} })
  expect(reset.ok()).toBe(true)
  expect(
    (await page.request.put('/api/settings/execution', { data: { profile: 'local' } })).ok(),
  ).toBe(true)
  await page.goto('/settings')
  await expect(analysis).toContainText('Local LLM')
  await analysis.click()
  await expect(page.getByRole('option', { name: /ChatGPT/ })).toBeDisabled()
  await expect(page.getByRole('option', { name: /Laya/ })).toHaveCount(0)
  await page.keyboard.press('Escape')
  await limits.click()
  await expect(page.getByRole('option', { name: /Laya/ })).toBeDisabled()
  await page.keyboard.press('Escape')

  await account.getByRole('button', { name: 'Continue with ChatGPT' }).click()
  await expect(page).toHaveURL(/\/settings\?chatgpt=connected$/)
  await expect(
    page.getByRole('status').filter({ hasText: 'Signed in with ChatGPT' }),
  ).toContainText('Signed in with ChatGPT')
  await expect(account).toContainText('synthetic@example.test')
  await page.getByRole('button', { name: 'Got it' }).click()
  await analysis.click()
  await page.getByRole('option', { name: 'ChatGPT', exact: true }).click()
  await expect(analysis).toContainText('ChatGPT')
  await expect(interviewer).toContainText('Local LLM')
  await expect(page.getByRole('note')).toContainText('send the required text to OpenAI')
  await page.reload()
  await expect(analysis).toContainText('ChatGPT')
  await page.screenshot({ path: 'test-results/tools-settings.png', fullPage: true })
  const scan = await new AxeBuilder({ page }).analyze()
  expect(scan.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical')).toEqual(
    [],
  )

  await page.goto('/')
  const tools = page.getByRole('region', { name: 'Active tools' })
  await expect(tools).toContainText('Document analysis')
  await expect(tools).toContainText('ChatGPT')
  await page.screenshot({ path: 'test-results/tools-dashboard.png', fullPage: true })
  await page.goto('/new-interview')
  await expect(page.getByRole('radio', { name: /ChatGPT|On this computer/ })).toHaveCount(0)
  await page.goto('/settings')

  // Signing out returns to the local profile.
  await account.getByRole('button', { name: 'Sign out of ChatGPT' }).click()
  await expect(analysis).toContainText('Local LLM')
  await analysis.click()
  await expect(page.getByRole('option', { name: /ChatGPT/ })).toBeDisabled()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('note')).toHaveCount(0)
})

test('a configured local model that is missing cannot be selected', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('probeloop.preferences', JSON.stringify({ language: 'en' }))
  })
  await page.route('**/api/settings/execution', async (route) => {
    const response = await route.fetch()
    const view = (await response.json()) as ExecutionView
    for (const role of view.tools)
      for (const option of role.options) {
        if (option.id === 'local') {
          option.available = false
          option.reason = 'model_missing'
        }
      }
    await route.fulfill({ json: view })
  })
  await page.goto('/settings')
  await page.getByRole('combobox', { name: 'Interviewer', exact: true }).click()
  await expect(page.getByRole('option', { name: /Local LLM/ })).toBeDisabled()
})

test('a Jev key is verified before use and its data use is stated', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('probeloop.preferences', JSON.stringify({ language: 'en' }))
  })
  let saved = false
  const scripted = (view: ExecutionView) => {
    if (!saved) return view
    view.jev.configured = true
    for (const role of view.tools)
      if (role.id === 'limits') {
        role.selected = 'jev'
        for (const option of role.options)
          if (option.id === 'jev') Object.assign(option, { available: true, reason: 'ready' })
      }
    return view
  }
  // No request reaches TypeSafe: the key check and the resulting state are scripted here.
  await page.route('**/api/settings/jev/key', async (route) => {
    const body = route.request().postDataJSON() as { key: string }
    if (body.key !== 'synthetic-accepted-key') {
      await route.fulfill({
        status: 422,
        json: { detail: 'the Jev API key was rejected; check it in Settings' },
      })
      return
    }
    saved = true
    const response = await page.request.get('/api/settings/execution')
    await route.fulfill({ json: scripted((await response.json()) as ExecutionView) })
  })
  await page.route('**/api/settings/execution', async (route) => {
    const response = await route.fetch()
    await route.fulfill({ json: scripted((await response.json()) as ExecutionView) })
  })
  await page.goto('/settings')
  const jev = page.getByRole('region', { name: 'Jev service' })
  const key = jev.getByLabel('Jev API key')
  await expect(key).toHaveAttribute('type', 'password')
  await key.fill('synthetic-wrong-key')
  await jev.getByRole('button', { name: 'Verify and save' }).click()
  await expect(jev.getByRole('alert')).toContainText('rejected')
  await key.fill('synthetic-accepted-key')
  await jev.getByRole('button', { name: 'Verify and save' }).click()
  await expect(jev).toContainText('Key saved')
  await expect(jev.getByLabel('Replace the API key')).toHaveValue('')
  await expect(page.getByRole('combobox', { name: 'Stated limits', exact: true })).toContainText(
    'Jev',
  )
  await expect(page.getByText('jev-1.14.0', { exact: true })).toBeVisible()
  await expect(jev.getByRole('note')).toContainText('sent to TypeSafe on every turn')
  const scan = await new AxeBuilder({ page }).analyze()
  expect(scan.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical')).toEqual(
    [],
  )
  await page.screenshot({ path: 'test-results/jev-settings.png', fullPage: true })
})

test('tool menus are locked while an interview is open', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('probeloop.preferences', JSON.stringify({ language: 'en' }))
  })
  await page.route('**/api/settings/execution', async (route) => {
    const response = await route.fetch()
    const view = (await response.json()) as ExecutionView
    await route.fulfill({ json: { ...view, locked: true, lock_reason: 'interview' } })
  })
  await page.goto('/settings')
  for (const role of [
    'Interviewer',
    'Document analysis',
    'Evaluations and reports',
    'Stated limits',
  ]) {
    await expect(page.getByRole('combobox', { name: role, exact: true })).toBeDisabled()
  }
  await expect(page.getByRole('status')).toHaveText(
    'Settings locked: close the active interview to change them.',
  )
})

test('the Italian preparation page has no serious accessibility violations', async ({ page }) => {
  await page.goto('/new-interview')
  await expect(
    page.getByRole('heading', { name: 'Impostazioni del colloquio', exact: true }),
  ).toBeVisible()
  await expect(page.getByRole('radio', { name: 'Tecnico', exact: true })).toBeVisible()
  const scan = await new AxeBuilder({ page }).analyze()
  expect(scan.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical')).toEqual(
    [],
  )
})
