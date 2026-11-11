import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'
import type { components } from '../src/shared/api/types/rest.js'

type InstallationView = components['schemas']['InstallationView']

function initial(): InstallationView {
  return {
    managed: true,
    locked: false,
    config: {
      completed: false,
      refinement: false,
      ollama_url: 'http://host.docker.internal:11434',
      limits_url: '',
    },
    local_models: {
      interviewer: 'synthetic-interviewer',
      analysis: 'synthetic-analysis',
      evaluation: 'synthetic-analysis',
      limits: 'synthetic-interviewer',
    },
    provisioning: {
      available: true,
      free_bytes: 12_000_000_000,
      memory_bytes: 8_000_000_000,
      cpus: 4,
      architecture: 'aarch64',
      models: [
        {
          id: 'laya',
          title: 'Stated limits · Laya',
          license: 'Apache-2.0',
          source: 'https://huggingface.co/submsk/probeloop-laya-stated-limits',
          bytes: 342_326_103,
          state: 'missing',
          download_available: false,
        },
      ],
    },
  }
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('probeloop.preferences', JSON.stringify({ language: 'en' }))
  })
})

test('an empty installation opens guided setup and keeps unavailable Laya disabled', async ({
  page,
}) => {
  const state = initial()
  await page.route('**/api/installation', (route) => route.fulfill({ json: state }))
  await page.goto('/')
  await expect(page).toHaveURL(/\/setup$/)
  await expect(page.getByRole('heading', { name: 'Welcome to ProbeLoop' })).toBeVisible()
  await expect(page.getByText('12.00 GB')).toBeVisible()
  await expect(page.getByText('aarch64', { exact: false })).toBeVisible()
  await expect(page.getByRole('checkbox', { name: /Second transcription/ })).not.toBeChecked()
  await page.getByRole('combobox', { name: 'Stated limits' }).click()
  await expect(page.getByRole('option', { name: /Laya/ })).toBeDisabled()
  await page.keyboard.press('Escape')
  const scan = await new AxeBuilder({ page }).analyze()
  expect(scan.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical')).toEqual(
    [],
  )
  await page.screenshot({ path: 'test-results/setup-desktop.png', fullPage: true })
})

test('installation settings save refinement explicitly and remain usable on mobile', async ({
  page,
}) => {
  let state = initial()
  state.config.completed = true
  await page.route('**/api/installation', async (route) => {
    if (route.request().method() === 'PUT') {
      const body = route.request().postDataJSON() as Omit<InstallationView['config'], 'completed'>
      state = { ...state, config: { ...state.config, ...body } }
    }
    await route.fulfill({ json: state })
  })
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/settings')
  const refinement = page.getByRole('checkbox', { name: /Second transcription/ })
  await expect(refinement).not.toBeChecked()
  await refinement.check()
  await page.getByRole('button', { name: 'Save configuration' }).click()
  await expect.poll(() => state.config.refinement).toBe(true)
  await expect(refinement).toBeChecked()
  const dimensions = await page.evaluate(() => ({
    content: document.documentElement.scrollWidth,
    viewport: window.innerWidth,
  }))
  expect(dimensions.content).toBeLessThanOrEqual(dimensions.viewport)
  await page.screenshot({ path: 'test-results/setup-settings-mobile.png', fullPage: true })
})

test('download progress survives a browser reload and locks installation changes', async ({
  page,
}) => {
  const state = initial()
  state.locked = true
  state.config.completed = true
  state.jobs = [
    {
      id: 'synthetic-download',
      kind: 'install_model',
      subject_id: 'laya',
      status: 'running',
      progress: 0.3,
      message: 'Downloading',
      error: null,
      result: null,
      created_at: 0,
      started_at: 0,
      finished_at: null,
    },
  ]
  await page.route('**/api/installation', (route) => route.fulfill({ json: state }))
  await page.goto('/settings')
  await expect(page.getByRole('progressbar', { name: 'Model download' })).toHaveAttribute(
    'aria-valuenow',
    '30',
  )
  await expect(page.getByRole('checkbox', { name: /Second transcription/ })).toBeDisabled()
  await page.reload()
  await expect(page.getByRole('progressbar', { name: 'Model download' })).toHaveAttribute(
    'aria-valuenow',
    '30',
  )
})
