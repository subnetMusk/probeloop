import { expect, test } from 'vitest'
import { parseLanguage } from './preferences'

test('language preferences tolerate missing, malformed and unknown data', () => {
  expect(parseLanguage(null)).toBe('it')
  expect(parseLanguage('broken')).toBe('it')
  expect(parseLanguage('{"language":"en"}')).toBe('en')
  expect(parseLanguage('{"language":"unknown"}')).toBe('it')
})
