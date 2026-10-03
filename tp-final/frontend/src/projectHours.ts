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


/** OLS slope over observed daily cumulative totals, anchored to the last actual balance. */
export function projectForecast(points: HoursPoint[], consumptions: HoursConsumption[], finish: string) {
  const lastDate = consumptions.reduce((last, row) => row.fecha_fin > last ? row.fecha_fin : last, '')
  const observed = points.filter(point => point.date <= lastDate)
  const values: (number | null)[] = points.map(() => null)
  if (!lastDate || lastDate >= finish || observed.length < 2) return { lastDate, values }
  const count = observed.length
  const meanX = (count - 1) / 2
  const meanY = observed.reduce((sum, point) => sum + point.actual, 0) / count
  let covariance = 0
  let variance = 0
  observed.forEach((point, index) => {
    covariance += (index - meanX) * (point.actual - meanY)
    variance += (index - meanX) ** 2
  })
  const slope = covariance / variance
  const last = observed[count - 1]!.actual
  for (let index = count - 1; index < points.length; index++) {
    if (points[index]!.date <= finish) values[index] = last + slope * (index - count + 1)
  }
  return { lastDate, values }
}
