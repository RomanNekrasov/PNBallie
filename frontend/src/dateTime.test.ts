import { describe, expect, it } from 'vitest'
import { formatLocalDateTime, parseUtcTimestamp } from './dateTime'

describe('UTC timestamps shown in local time', () => {
  it('interprets old SQLite timestamps as UTC, and preserves explicit offsets', () => {
    expect(parseUtcTimestamp('2026-01-05T12:30:00').toISOString()).toBe('2026-01-05T12:30:00.000Z')
    expect(parseUtcTimestamp('2026-01-05 12:30:00').toISOString()).toBe('2026-01-05T12:30:00.000Z')
    expect(parseUtcTimestamp('2026-01-05T13:30:00+01:00').toISOString()).toBe('2026-01-05T12:30:00.000Z')
  })

  it('accounts for Amsterdam winter/summer offsets and midnight rollover', () => {
    expect(formatLocalDateTime('2026-01-05T12:30:00Z', 'Europe/Amsterdam')).toContain('13:30')
    expect(formatLocalDateTime('2026-07-05T12:30:00Z', 'Europe/Amsterdam')).toContain('14:30')
    expect(formatLocalDateTime('2026-07-05T23:30:00Z', 'Europe/Amsterdam')).toMatch(/6 jul.*01:30/)
  })

  it('jumps over the spring DST gap without changing the instant', () => {
    expect(formatLocalDateTime('2026-03-29T00:59:00Z', 'Europe/Amsterdam')).toContain('01:59')
    expect(formatLocalDateTime('2026-03-29T01:00:00Z', 'Europe/Amsterdam')).toContain('03:00')
  })

  it('uses the requested viewer timezone without always forcing Amsterdam', () => {
    expect(formatLocalDateTime('2026-07-05T12:30:00Z', 'America/New_York')).toContain('08:30')
    expect(formatLocalDateTime('invalid')).toBe('Onbekend tijdstip')
  })
})
