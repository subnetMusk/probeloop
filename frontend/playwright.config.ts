import path from 'node:path'

import { defineConfig, devices } from '@playwright/test'

// Chromium's fake microphone plays this synthetic answer in a loop (see backend fixtures).
const fakeMicrophone = path.resolve(
  import.meta.dirname,
  '../backend/tests/fixtures/synthetic/speech/long_answer.wav',
)

/**
 * End-to-end tests against a running backend with fake engines:
 *   docker compose -f compose.yaml -f compose.test.yaml up -d --no-deps backend
 */
export default defineConfig({
  testDir: 'e2e',
  workers: 1,
  timeout: 120_000,
  retries: process.env.CI ? 1 : 0,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    ...devices['Desktop Chrome'],
    baseURL: process.env.PROBELOOP_E2E_URL ?? 'http://127.0.0.1:8000',
    trace: 'retain-on-failure',
    permissions: ['microphone'],
    launchOptions: {
      args: [
        '--use-fake-ui-for-media-stream',
        '--use-fake-device-for-media-stream',
        `--use-file-for-fake-audio-capture=${fakeMicrophone}`,
        '--autoplay-policy=no-user-gesture-required',
      ],
    },
  },
})
