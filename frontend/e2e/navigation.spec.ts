import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'

test('pages are named by the same slug in the URL, the tab and the breadcrumbs', async ({
  page,
}) => {
  await page.goto('/')
  await expect(page).toHaveURL(/\/dashboard$/)
  await expect(page).toHaveTitle('dashboard | ProbeLoop')

  await page
    .getByRole('navigation', { name: 'Principale' })
    .getByRole('link', {
      name: 'Nuovo colloquio',
    })
    .click()
  // The preparation opens at its first incomplete step.
  await expect(page).toHaveURL(/\/new-interview\/interview-settings$/)
  await expect(page).toHaveTitle('interview-settings | ProbeLoop')
  const trail = page.getByRole('navigation', { name: 'Percorso' })
  await expect(trail.getByRole('link', { name: 'dashboard' })).toBeVisible()
  await expect(trail.getByRole('link', { name: 'new-interview' })).toBeVisible()
  await expect(trail.locator('[aria-current="page"]')).toHaveText('interview-settings')

  await expect(page.getByRole('link', { name: 'subnetMusk' })).toHaveAttribute(
    'href',
    'https://github.com/subnetMusk/',
  )
  await page.getByRole('link', { name: /Dichiarazione di accessibilità/ }).click()
  await expect(page).toHaveURL(/\/accessibility$/)
  await expect(page).toHaveTitle('accessibility | ProbeLoop')
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Dichiarazione di accessibilità')
  const scan = await new AxeBuilder({ page }).analyze()
  expect(scan.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical')).toEqual(
    [],
  )

  const icon = await page.locator('link[rel="icon"]').getAttribute('href')
  expect(icon).not.toBeNull()
  const favicon = await page.request.get(icon ?? '')
  expect(favicon.headers()['content-type']).toContain('image/svg+xml')

  await page.goto('/no-such-page')
  await expect(page).toHaveTitle('not-found | ProbeLoop')
  await expect(page.getByRole('heading', { name: 'Pagina non trovata' })).toBeVisible()
})
