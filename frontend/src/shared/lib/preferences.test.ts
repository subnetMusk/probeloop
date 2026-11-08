import { expect, test } from 'vitest'
import { parseLanguage, parsePreferences } from './preferences'

test('language preferences tolerate missing, malformed and unknown data', () => {
  expect(parseLanguage(null)).toBe('it')
  expect(parseLanguage('broken')).toBe('it')
  expect(parseLanguage('{"language":"en"}')).toBe('en')
  expect(parseLanguage('{"language":"unknown"}')).toBe('it')
})

test('theme and volume preferences survive legacy data and clamp malformed values', () => {
  expect(parsePreferences('{"language":"en"}')).toEqual({
    language: 'en',
    volume: 1,
    theme: 'system',
  })
  expect(parsePreferences('{"volume":2,"theme":"dark"}')).toEqual({
    language: 'it',
    volume: 1,
    theme: 'dark',
  })
  expect(parsePreferences('{"volume":-1,"theme":"unknown"}')).toEqual({
    language: 'it',
    volume: 0,
    theme: 'system',
  })
  expect(parsePreferences('{"volume":"quiet"}').volume).toBe(1)
})
