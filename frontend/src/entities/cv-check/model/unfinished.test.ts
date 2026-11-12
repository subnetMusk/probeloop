import { expect, test } from 'vitest'
import { parsePreparationIds } from './unfinished'

test('remembered CV check preparations accept identifiers and reject malformed storage', () => {
  expect(parsePreparationIds(null)).toEqual([])
  expect(parsePreparationIds('invalid')).toEqual([])
  expect(parsePreparationIds('{"id":"abc"}')).toEqual([])
  expect(parsePreparationIds('["01a1d0a8",null,2,"<script>"]')).toEqual(['01a1d0a8'])
  const many = Array.from({ length: 25 }, (_, i) => `p${String(i)}`)
  expect(parsePreparationIds(JSON.stringify(many))).toEqual(many.slice(-20))
})
