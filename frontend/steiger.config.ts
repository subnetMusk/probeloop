import fsd from '@feature-sliced/steiger-plugin'
import { defineConfig } from 'steiger'

// Feature-Sliced Design rules (ADR 0014). `src/legacy` holds screens that the redesign replaces;
// it is checked by ESLint only and removed slice by slice.
export default defineConfig([
  ...fsd.configs.recommended,
  { ignores: ['./src/legacy/**', './src/shared/api/types/**', './src/shared/api/contract/**'] },
  {
    // Slices used once are expected while the redesign is in progress.
    rules: { 'fsd/insignificant-slice': 'off' },
  },
])
