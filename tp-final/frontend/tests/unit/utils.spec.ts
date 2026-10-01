import { describe, expect, it } from 'vitest'
import { dateRangeError } from '@/utils'

describe('dateRangeError', () => {
  it('accepts equal start and end dates', () => {
    expect(dateRangeError('2026-09-01', '2026-09-01')).toBeNull()
  })
  it('accepts an end date after the start date', () => {
    expect(dateRangeError('2026-09-01', '2026-09-30')).toBeNull()
  })
  it('rejects an end date before the start date, with the backend message', () => {
    expect(dateRangeError('2026-10-02', '2026-10-01')).toBe('La fecha de fin no puede ser anterior al inicio.')
  })
  it('stays quiet when either date is missing (handled separately as "both required")', () => {
    expect(dateRangeError('', '2026-09-30')).toBeNull()
    expect(dateRangeError('2026-09-01', '')).toBeNull()
    expect(dateRangeError('', '')).toBeNull()
  })
})
