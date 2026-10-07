export type HoursProject = { fecha_inicio: string; fecha_fin: string; horas_requeridas: number }
export type HoursConsumption = { fecha_inicio: string; fecha_fin: string; horas_consumidas: number }
export type HoursPoint = { date: string; planned: number; actual: number }
const DAY = 86400000
const dayNumber = (date: string) => Date.parse(date) / DAY

/** Inclusive calendar dates in UTC; each consumption is distributed evenly across its period. */
export function projectHours(project: HoursProject, consumptions: HoursConsumption[]): HoursPoint[] {
  const start = dayNumber(project.fecha_inicio)
  const finish = dayNumber(project.fecha_fin)
  let end = finish
  const changes = new Map<number, number>()
  const add = (day: number, value: number) => changes.set(day, (changes.get(day) ?? 0) + value)
  let actual = 0
  for (const consumption of consumptions) {
    const from = dayNumber(consumption.fecha_inicio)
    const to = dayNumber(consumption.fecha_fin)
    const daily = consumption.horas_consumidas / (to - from + 1)
    end = Math.max(end, to)
    // Include any hours prior to the project in the first visible accumulated balance.
    actual += Math.max(0, Math.min(to + 1, start) - from) * daily
    if (to >= start) {
      add(Math.max(start, from), daily)
      add(to + 1, -daily)
    }
  }
  const points: HoursPoint[] = []
  let rate = 0
  for (let day = start; day <= end; day++) {
    rate += changes.get(day) ?? 0
    actual += rate
    points.push({
      date: new Date(day * DAY).toISOString().slice(0, 10),
      planned: project.horas_requeridas * Math.min((day - start + 1) / (finish - start + 1), 1),
      actual: Math.max(0, actual),
    })
  }
  return points
}


type Trend = { slope: number; last: number; count: number }

/** OLS slope over observed daily cumulative totals, anchored to the last actual balance. */
function trend(points: HoursPoint[], lastDate: string): Trend | null {
  const observed = points.filter(point => point.date <= lastDate)
  if (!lastDate || observed.length < 2) return null
  const count = observed.length
  const meanX = (count - 1) / 2
  const meanY = observed.reduce((sum, point) => sum + point.actual, 0) / count
  let covariance = 0
  let variance = 0
  observed.forEach((point, index) => {
    covariance += (index - meanX) * (point.actual - meanY)
    variance += (index - meanX) ** 2
  })
  return { slope: covariance / variance, last: observed[count - 1]!.actual, count }
}

const lastConsumptionDate = (consumptions: HoursConsumption[]) =>
  consumptions.reduce((last, row) => row.fecha_fin > last ? row.fecha_fin : last, '')

export function projectForecast(points: HoursPoint[], consumptions: HoursConsumption[], finish: string) {
  const lastDate = lastConsumptionDate(consumptions)
  const values: (number | null)[] = points.map(() => null)
  const fit = trend(points, lastDate)
  if (!fit || lastDate >= finish) return { lastDate, values, slope: fit?.slope ?? null }
  for (let index = fit.count - 1; index < points.length; index++) {
    if (points[index]!.date <= finish) values[index] = fit.last + fit.slope * (index - fit.count + 1)
  }
  return { lastDate, values, slope: fit.slope }
}

export type ForecastStatus = { text: string; acceptable: boolean }

/** Projected hours at the planned end against the required ones (±15 %). */
export function forecastStatus(projected: number | null, required: number): ForecastStatus | null {
  if (projected === null) return null
  const ratio = projected / required
  // Tolerance only compensates floating-point noise at the inclusive boundaries.
  if (ratio > 1.15 + 1e-12) return { text: 'Sobre aplicacion', acceptable: false }
  if (ratio < 0.85 - 1e-12) return { text: 'Falta de Recursos', acceptable: false }
  return { text: 'Aceptable', acceptable: true }
}

const addDays = (date: string, days: number) => new Date(Date.parse(date) + days * DAY).toISOString().slice(0, 10)

/**
 * Day on which the cumulative hours reach `required`: the first real day if they already did,
 * otherwise the regression line from the last recorded day (also for overdue projects).
 * Null when there is no usable trend (fewer than 2 days of data, or a flat/negative slope).
 */
export function projectedEndDate(points: HoursPoint[], consumptions: HoursConsumption[], required: number) {
  const reached = points.find(point => point.actual >= required - 1e-9)
  if (reached) return reached.date
  const lastDate = lastConsumptionDate(consumptions)
  const fit = trend(points, lastDate)
  if (!fit || fit.slope <= 0) return null
  return addDays(lastDate, Math.ceil((required - fit.last) / fit.slope - 1e-9))
}
