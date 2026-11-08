import { expect, test } from 'vitest'
import { parseJobs } from './pending-jobs'

test('notification recovery accepts job identifiers and rejects malformed storage', () => {
  expect(parseJobs('invalid')).toEqual([])
  expect(parseJobs('["abc-123",null,2,"<script>"]')).toEqual(['abc-123'])
})
