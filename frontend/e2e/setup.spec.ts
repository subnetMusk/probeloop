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
    if (!localStorage.getItem('probeloop.preferences'))
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
  await expect(page.getByRole('switch', { name: /Second transcription/ })).not.toBeChecked()
  await page.getByRole('combobox', { name: 'Stated limits' }).click()
  await expect(page.getByRole('option', { name: /Laya/ })).toBeDisabled()
  await expect(page.getByRole('option', { name: /Jev.*Add a Jev API key/ })).toBeDisabled()
  await page.keyboard.press('Escape')
  // Laya is optional: the one-click installation covers speech only.
  await expect(page.getByRole('button', { name: 'Install speech components' })).toBeVisible()
  await expect(page.getByText(/^Optional\. Reads stated limits/)).toBeVisible()
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
  const refinement = page.getByRole('switch', { name: /Second transcription/ })
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
  state.lock_reason = 'background_job'
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
  await expect(page.getByRole('progressbar', { name: 'Model progress' })).toHaveAttribute(
    'aria-valuenow',
    '30',
  )
  await expect(page.getByRole('switch', { name: /Second transcription/ })).toBeDisabled()
  await page.reload()
  await expect(page.getByRole('progressbar', { name: 'Model progress' })).toHaveAttribute(
    'aria-valuenow',
    '30',
  )
})

test('existing Whisper verification explains progress and unlocks both settings panels', async ({
  page,
}) => {
  const state = initial()
  state.config.completed = true
  state.config.refinement = true
  state.locked = true
  state.lock_reason = 'background_job'
  state.provisioning.models = [
    {
      ...state.provisioning.models[0],
      id: 'whisper',
      title: 'Whisper',
      state: 'unverified',
      download_available: true,
    },
  ]
  state.jobs = [
    {
      id: 'synthetic-whisper-verification',
      kind: 'install_model',
      subject_id: 'whisper',
      status: 'running',
      progress: 0.08,
      message: 'Checking installed model files',
      error: null,
      result: null,
      created_at: 0,
      started_at: 0,
      finished_at: null,
    },
  ]
  await page.route('**/api/installation', (route) => route.fulfill({ json: state }))
  await page.route('**/api/settings/execution', async (route) => {
    const response = await route.fetch()
    const execution = (await response.json()) as components['schemas']['ExecutionView']
    await route.fulfill({
      json: { ...execution, locked: state.locked, lock_reason: state.lock_reason },
    })
  })
  await page.goto('/settings')
  await page.evaluate(() => {
    localStorage.setItem('probeloop.preferences', JSON.stringify({ language: 'it' }))
  })
  await page.reload()
  await expect(page.getByText('File già presenti.', { exact: false })).toBeVisible()
  for (const name of ['Trascrizione ricostruita', 'Seconda trascrizione con Whisper']) {
    const control = page.getByRole('switch', { name })
    const width = await control.evaluate((element) => {
      const row = element.closest('label')
      const card = row?.parentElement
      if (!row || !card) throw new Error('Missing switch row')
      return {
        actual: row.getBoundingClientRect().width,
        parent: card.getBoundingClientRect().width,
        isGrid: getComputedStyle(card).display === 'grid',
      }
    })
    expect(width.actual).toBeGreaterThan(width.parent - (width.isGrid ? 2 : 36))
  }
  await expect(page.getByText('Verifica dei file già presenti · 8%')).toBeVisible()
  const lock = page.getByText('Impostazioni bloccate: attendi', { exact: false })
  await expect(lock).toHaveCount(2)
  await expect(page.getByText('chiudi il colloquio attivo', { exact: false })).toHaveCount(0)
  const refinement = page.getByRole('switch', { name: /Seconda trascrizione/ })
  await expect(refinement).toBeDisabled()
  state.jobs[0].progress = 0.17
  await expect(page.getByText('Verifica dei file già presenti · 17%')).toBeVisible({
    timeout: 10_000,
  })
  await expect(page.getByRole('progressbar', { name: 'Avanzamento del modello' })).toHaveAttribute(
    'aria-valuenow',
    '17',
  )
  state.jobs[0].status = 'succeeded'
  state.jobs[0].progress = 1
  state.jobs[0].message = 'Model installed and verified'
  state.provisioning.models[0].state = 'ready'
  state.locked = false
  state.lock_reason = null
  await expect(lock).toHaveCount(0, { timeout: 10_000 })
  await expect(refinement).toBeEnabled()
  await expect(page.getByRole('progressbar')).toHaveCount(0)
  await expect(page.getByRole('combobox', { name: 'Intervistatore' })).toBeEnabled()
})
