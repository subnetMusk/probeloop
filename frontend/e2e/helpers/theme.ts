import type { Page } from '@playwright/test'

/** Scan the settled theme, after finite colour and layout transitions finish. */
export async function setTheme(page: Page, theme: string) {
  await page.evaluate(async (theme) => {
    document.documentElement.classList.toggle('dark', theme === 'dark')
    const transitions = document
      .getAnimations()
      .filter((animation) => animation.effect?.getTiming().iterations !== Infinity)
    await Promise.all(transitions.map((animation) => animation.finished.catch(() => undefined)))
  }, theme)
}
