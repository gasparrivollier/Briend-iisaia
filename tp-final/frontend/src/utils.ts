const numberFormat = new Intl.NumberFormat('es-AR', { maximumFractionDigits: 2 })

export const fmt = (value: number | null | undefined) => numberFormat.format(value ?? 0)

export const statusClass = (status: string) => 'status status-' + status.toLowerCase().replaceAll(' ', '-')

/** Form inputs hold strings; an empty field becomes NaN (sent as null) so the API rejects it. */
export const toNumber = (value: string | number | null | undefined) =>
  value === '' || value === null || value === undefined ? Number.NaN : Number(value)

export const toText = (value: string | number | null | undefined) =>
  value === null || value === undefined ? '' : String(value)

/**
 * Null when the range is valid; otherwise the message to show inline. ISO 'YYYY-MM-DD'
 * strings compare correctly with plain string ordering. Mirrors the backend's own
 * start<=end check (DateRange.ordered in backend/pulso/schemas.py) so the message matches.
 */
export const dateRangeError = (start: string, end: string): string | null =>
  !start || !end ? null : end < start ? 'La fecha de fin no puede ser anterior al inicio.' : null
