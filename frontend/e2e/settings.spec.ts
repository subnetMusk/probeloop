import { expect, test } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'

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
test('the ChatGPT plan profile needs a sign-in and a confirmation', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('probeloop.preferences', JSON.stringify({ language: 'en' }))
  })
  const local = page.getByRole('radio', { name: /^Local/ })
  const cloud = page.getByRole('radio', { name: /^ChatGPT plan/ })
  const account = page.getByRole('region', { name: 'ChatGPT account' })
  const reset = await page.request.post('/api/settings/chatgpt/sign-out', { data: {} })
  expect(reset.ok()).toBe(true)
  await page.goto('/settings')
  await expect(local).toBeChecked()
  await expect(cloud).toBeDisabled()
  await expect(account).toContainText('Use your ChatGPT plan')

  await account.getByRole('button', { name: 'Continue with ChatGPT' }).click()
  await expect(page).toHaveURL(/\/settings\?chatgpt=connected$/)
  await expect(page.getByRole('status')).toContainText('Signed in with ChatGPT')
  await expect(account).toContainText('synthetic@example.test')
  await page.getByRole('button', { name: 'Got it' }).click()
  await expect(page.getByRole('status')).toHaveCount(0)

  page.once('dialog', (dialog) => void dialog.dismiss())
  await cloud.click()
  await expect(local).toBeChecked()
  page.once('dialog', (dialog) => {
    expect(dialog.message()).toContain('sent to OpenAI')
    void dialog.accept()
  })
  await cloud.click()
  await expect(cloud).toBeChecked()
  await expect(page.getByRole('note')).toContainText('Using ChatGPT plan')
  await page.reload()
  await expect(cloud).toBeChecked()

  // Signing out returns to the local profile.
  await account.getByRole('button', { name: 'Sign out of ChatGPT' }).click()
  await expect(local).toBeChecked()
  await expect(cloud).toBeDisabled()
  await expect(page.getByRole('note')).toHaveCount(0)
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
