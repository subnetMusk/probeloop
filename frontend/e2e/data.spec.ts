import { expect, test } from '@playwright/test'
import { readFileSync } from 'node:fs'

// The backend runs with scripted models (compose.test.yaml) on its own test volume. This test
// deletes all application data in that volume; the other tests seed what they need.

interface Exported {
  format: string
  revision: string
  tables: Partial<Record<string, Record<string, unknown>[]>>
}

test('data is exported, backed up and deleted from Settings', async ({ page, request }) => {
  const name = `Data profile ${String(Date.now())}`
  const document = (await (
    await request.post('/api/documents/text', {
      data: { kind: 'cv', title: 'CV', text: 'Giulia Neri, synthetic backend developer.' },
    })
  ).json()) as { id: string }
  await request.post('/api/profiles', { data: { name, cv_id: document.id, resources: [] } })

  await page.goto('/settings')
  await page.evaluate(() => {
    localStorage.setItem('probeloop.preferences', JSON.stringify({ language: 'en' }))
    localStorage.setItem('probeloop.guide-seen', '1')
    localStorage.setItem('probeloop.getting-started-hidden', '1')
  })
  await page.reload()

  const exported = page.waitForEvent('download')
  await page.getByRole('button', { name: 'JSON', exact: true }).click()
  const json = await exported
  expect(json.suggestedFilename()).toMatch(/^probeloop-data-\d{8}-\d{6}\.json$/)
  const data = JSON.parse(readFileSync(await json.path(), 'utf8')) as Exported
  expect(data.tables.profiles?.some((row) => row.name === name)).toBe(true)
  expect(data.revision).toMatch(/^\d{4}$/)

  const backedUp = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Download ZIP backup', exact: true }).click()
  const zip = await backedUp
  expect(zip.suggestedFilename()).toMatch(/^probeloop-backup-\d{8}-\d{6}\.zip$/)
  expect(
    readFileSync(await zip.path())
      .subarray(0, 2)
      .toString(),
  ).toBe('PK')

  page.once('dialog', (dialog) => void dialog.accept())
  await page.getByRole('button', { name: 'Delete all my data', exact: true }).click()
  await expect(page).toHaveURL(/\/settings\?deleted=1$/)
  await expect(
    page
      .getByRole('status')
      .filter({ hasText: /Application data deleted|dati dell’app sono stati/ }),
  ).toHaveCount(1)
  const marks = await page.evaluate(() => [
    localStorage.getItem('probeloop.guide-seen'),
    localStorage.getItem('probeloop.getting-started-hidden'),
  ])
  expect(marks).toEqual([null, null])
  expect(await (await request.get('/api/profiles')).json()).toEqual([])
  const summary = (await (await request.get('/api/data/summary')).json()) as Record<string, number>
  expect(Object.values(summary).every((count) => count === 0)).toBe(true)
})
