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

// The test backend scripts every model, and its cloud profile reuses the scripted models.
test('the cloud execution profile is selected only after confirmation', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('probeloop.preferences', JSON.stringify({ language: 'en' }))
  })
  const reset = await page.request.put('/api/settings/execution', { data: { profile: 'local' } })
  expect(reset.ok()).toBe(true)
  await page.goto('/settings')
  const local = page.getByRole('radio', { name: /^Local/ })
  const cloud = page.getByRole('radio', { name: /^Cloud/ })
  await expect(local).toBeChecked()
  page.once('dialog', (dialog) => void dialog.dismiss())
  await cloud.click()
  await expect(local).toBeChecked()
  page.once('dialog', (dialog) => {
    expect(dialog.message()).toContain('sent to the cloud provider')
    void dialog.accept()
  })
  await cloud.click()
  await expect(cloud).toBeChecked()
  await expect(page.getByRole('note')).toContainText('Cloud profile active')
  await page.reload()
  await expect(cloud).toBeChecked()
  await local.click()
  await expect(local).toBeChecked()
  await expect(page.getByRole('note')).toHaveCount(0)
})

test('the Italian preparation page has no serious accessibility violations', async ({ page }) => {
  await page.goto('/')
  await expect(
    page.getByRole('heading', { name: 'Prepara il colloquio', exact: true }),
  ).toBeVisible()
  const scan = await new AxeBuilder({ page }).analyze()
  expect(scan.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical')).toEqual(
    [],
  )
})
