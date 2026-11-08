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
