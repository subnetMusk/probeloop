import { expect, test } from '@playwright/test'

for (const width of [1280, 1440]) {
  for (const theme of ['light', 'dark']) {
    test(`dashboard cards align at ${String(width)}px in ${theme}`, async ({ page }) => {
      await page.setViewportSize({ width, height: 720 })
      await page.addInitScript((theme) => {
        localStorage.setItem('probeloop.preferences', JSON.stringify({ language: 'en', theme }))
      }, theme)
      await page.goto('/dashboard')
      await expect(page.getByTestId('interview-row').first()).toBeVisible()
      const cards = page.locator('main [data-slot="card"]')
      await expect(cards).toHaveCount(5)
      const boxes = await cards.evaluateAll((elements) =>
        elements.map((element) => {
          const { x, y, width, height } = element.getBoundingClientRect()
          return { x, y, width, height }
        }),
      )
      for (const group of [boxes.slice(0, 2), boxes.slice(2)]) {
        for (const box of group) {
          expect(box.y).toBe(group[0]?.y)
          expect(Math.abs(box.width - (group[0]?.width ?? 0))).toBeLessThan(1)
          expect(box.height).toBe(group[0]?.height)
        }
      }
      await page.screenshot({ path: `test-results/dashboard-${String(width)}-${theme}.png` })
      const content = page.getByTestId('content')
      await content.evaluate((element) => {
        element.scrollTo({ top: element.scrollHeight })
      })
      const top = page.getByRole('button', { name: 'Back to top' })
      await expect(top).toBeVisible()
      await page.screenshot({ path: `test-results/dashboard-${String(width)}-${theme}-lists.png` })
      const button = await top.boundingBox()
      const main = await page.locator('main').boundingBox()
      expect(button?.x).toBeGreaterThanOrEqual((main?.x ?? 0) + (main?.width ?? 0) - 24)
      expect(await page.evaluate(() => window.scrollY)).toBe(0)
    })
  }
}
