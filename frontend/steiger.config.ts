import fsd from '@feature-sliced/steiger-plugin'
import { defineConfig } from 'steiger'

// Feature-Sliced Design rules (ADR 0014).
export default defineConfig([
  ...fsd.configs.recommended,
  { ignores: ['./src/shared/api/types/**', './src/shared/api/contract/**'] },
  {
    // Slices used once are expected while the redesign is in progress.
    rules: { 'fsd/insignificant-slice': 'off' },
  },
])
