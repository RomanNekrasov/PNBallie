/** SQLite legacy timestamps are UTC even when their timezone suffix is missing. */
export function parseUtcTimestamp(value: string): Date {
  const normalized = value.trim().replace(' ', 'T')
  return new Date(/(?:Z|[+-]\d{2}:?\d{2})$/i.test(normalized) ? normalized : `${normalized}Z`)
}

/** Display the instant in the viewer's local timezone; timezone can be explicit for exports/tests. */
export function formatLocalDateTime(value: string, timeZone?: string): string {
  const date = parseUtcTimestamp(value)
  if (!Number.isFinite(date.getTime())) return 'Onbekend tijdstip'
  return new Intl.DateTimeFormat('nl-NL', {
    weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit',
    ...(timeZone ? { timeZone } : {}),
  }).format(date)
}
