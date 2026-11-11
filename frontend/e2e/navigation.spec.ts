import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'

test('page names are localised in tabs and breadcrumbs while URLs keep their slugs', async ({
  page,
}) => {
  await page.goto('/')
  await expect(page).toHaveURL(/\/dashboard$/)
  await expect(page).toHaveTitle('Dashboard | ProbeLoop')

  await page
    .getByRole('navigation', { name: 'Principale' })
    .getByRole('link', {
      name: 'Nuovo colloquio',
    })
    .click()
  // The preparation opens at its first incomplete step.
  await expect(page).toHaveURL(/\/new-interview\/interview-settings$/)
  await expect(page).toHaveTitle('Impostazioni del colloquio | ProbeLoop')
  const trail = page.getByRole('navigation', { name: 'Percorso' })
  await expect(trail.getByRole('link', { name: 'Dashboard' })).toBeVisible()
  await expect(trail.getByRole('link', { name: 'Nuovo colloquio' })).toBeVisible()
  await expect(trail.locator('[aria-current="page"]')).toHaveText('Impostazioni del colloquio')

  await expect(page.getByRole('link', { name: 'subnetMusk' })).toHaveAttribute(
    'href',
    'https://github.com/subnetMusk/',
  )
  await page.getByRole('link', { name: /Dichiarazione di accessibilità/ }).click()
  await expect(page).toHaveURL(/\/accessibility$/)
  await expect(page).toHaveTitle('Accessibilità | ProbeLoop')
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
  await expect(page).toHaveTitle('Pagina non trovata | ProbeLoop')
  await expect(page.getByRole('heading', { name: 'Pagina non trovata' })).toBeVisible()
})

for (const start of ['/guide', '/dashboard']) {
  test(`the mobile logo closes the menu from ${start}`, async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 })
    await page.goto(start)
    const trigger = page.getByTestId('menu-open')
    await trigger.click()
    const menu = page.getByRole('dialog', { name: 'Menu', exact: true })
    await expect(menu).toBeVisible()
    const logo = menu.getByRole('link', { name: 'ProbeLoop, dashboard' })
    if (start === '/dashboard') await logo.press('Enter')
    else await logo.click()
    await expect(page).toHaveURL(/\/dashboard$/)
    await expect(menu).toBeHidden()
    await expect(trigger).toBeFocused()
    await expect(page.getByRole('heading', { level: 1, name: 'Dashboard' })).toBeVisible()
    await page.screenshot({
      path: `test-results/mobile-logo-${start.slice(1)}.png`,
    })
  })
}

for (const language of ['it', 'en']) {
  for (const path of ['/no-such-page', '/settings/no-such-page']) {
    test(`missing page titles are localised in ${language} at ${path}`, async ({ page }) => {
      await page.addInitScript((language) => {
        localStorage.setItem('probeloop.preferences', JSON.stringify({ language }))
      }, language)
      await page.goto(path)
      const title = language === 'it' ? 'Pagina non trovata' : 'Page not found'
      await expect(page.getByRole('heading', { level: 1, name: title })).toBeVisible()
      await expect(page).toHaveTitle(`${title} | ProbeLoop`)
      await page.screenshot({
        path: `test-results/not-found-${language}-${path.split('/').length}.png`,
      })
      const settings = language === 'it' ? 'Impostazioni' : 'Settings'
      const navigation = language === 'it' ? 'Principale' : 'Main'
      await page
        .getByRole('navigation', { name: navigation })
        .getByRole('link', { name: settings, exact: true })
        .click()
      await expect(page).toHaveTitle(`${settings} | ProbeLoop`)
      await page.goBack()
      await expect(page.getByRole('heading', { level: 1, name: title })).toBeVisible()
      await expect(page).toHaveTitle(`${title} | ProbeLoop`)
    })
  }
}

for (const width of [375, 1440]) {
  test(`the arrow-only back-to-top control works on a long page at ${String(width)}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 720 })
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await page.goto('/guide')
    const content = page.getByTestId('content')
    await content.evaluate((element) => {
      element.scrollTo({ top: element.scrollHeight })
    })
    const top = page.getByRole('button', { name: 'Torna su', exact: true })
    await expect(top).toBeVisible()
    await expect(top).toHaveText('')
    const size = await top.evaluate((element) => {
      const { width, height } = element.getBoundingClientRect()
      return { width, height }
    })
    expect(size.width).toBe(size.height)
    await top.click()
    await expect.poll(() => content.evaluate((element) => element.scrollTop)).toBe(0)
    await expect(page.getByRole('heading', { level: 1 })).toBeFocused()
  })
}
