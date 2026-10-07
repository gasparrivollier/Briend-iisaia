import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { projectHours, projectForecast, forecastStatus, projectedEndDate } from '@/projectHours'
import ProjectHoursChart from '@/components/ProjectHoursChart.vue'

const project = { fecha_inicio: '2026-10-01', fecha_fin: '2026-10-03', horas_requeridas: 36 }
describe('cumulative project hours', () => {
  it('includes both dates and ends exactly at the required hours', () => {
    const points = projectHours(project, [])
    expect(points.map(p => p.planned)).toEqual([12, 24, 36])
    expect(points.map(p => p.actual)).toEqual([0, 0, 0])
  })
  it('distributes overlapping consumptions across their dates', () => {
    const points = projectHours(project, [
      { fecha_inicio: '2026-10-01', fecha_fin: '2026-10-03', horas_consumidas: 9 },
      { fecha_inicio: '2026-10-02', fecha_fin: '2026-10-02', horas_consumidas: 5 },
    ])
    expect(points.map(p => p.actual)).toEqual([3, 11, 14])
  })
  it('retains previous hours and extends beyond the planned end without inflating the plan', () => {
    const points = projectHours(project, [
      { fecha_inicio: '2026-09-29', fecha_fin: '2026-10-01', horas_consumidas: 9 },
      { fecha_inicio: '2026-10-03', fecha_fin: '2026-10-04', horas_consumidas: 10 },
    ])
    expect(points.map(p => p.actual)).toEqual([9, 9, 14, 19])
    expect(points.at(-1)).toEqual({ date: '2026-10-04', planned: 36, actual: 19 })
  })
  it('supports single-day and leap-year periods', () => {
    expect(projectHours({ ...project, fecha_fin: project.fecha_inicio }, [
      { fecha_inicio: project.fecha_inicio, fecha_fin: project.fecha_inicio, horas_consumidas: 6 },
    ])).toEqual([{ date: project.fecha_inicio, planned: 36, actual: 6 }])
    expect(projectHours({ ...project, fecha_inicio: '2028-02-28', fecha_fin: '2028-03-01' }, [])).toHaveLength(3)
  })
  it('shows both lines and lets the user inspect individual days', async () => {
    const wrapper = mount(ProjectHoursChart, { props: { project, consumptions: [] } })
    expect(wrapper.findAll('path')).toHaveLength(2)
    expect(wrapper.text()).toContain('Sin consumos registrados')
    await wrapper.get('input[type="range"]').setValue(0)
    expect(wrapper.get('.chart-values').text()).toContain('01/10/2026')
    expect(wrapper.get('.chart-values').text()).toContain('Planificadas: 12 h')
    await wrapper.setProps({ consumptions: [{ fecha_inicio: project.fecha_inicio, fecha_fin: project.fecha_fin, horas_consumidas: 40 }] })
    expect(wrapper.get('.overrun').text()).toContain('Exceso: 4 h')
    expect(wrapper.get('.chart-values').text()).toContain('Aplicadas: 40 h')
    wrapper.unmount()
  })
})


describe('linear forecast', () => {
  const plan = { fecha_inicio: '2026-10-01', fecha_fin: '2026-10-05', horas_requeridas: 100 }
  it('fits daily cumulative values and excludes future zero-consumption days', () => {
    const rows = [{ fecha_inicio: '2026-10-01', fecha_fin: '2026-10-03', horas_consumidas: 30 }]
    const forecast = projectForecast(projectHours(plan, rows), rows, plan.fecha_fin)
    expect(forecast.lastDate).toBe('2026-10-03')
    expect(forecast.values).toEqual([null, null, 30, 40, 50])
  })
  it('uses the least-squares slope and connects to the last real point', () => {
    const rows = [
      { fecha_inicio: '2026-10-01', fecha_fin: '2026-10-01', horas_consumidas: 2 },
      { fecha_inicio: '2026-10-02', fecha_fin: '2026-10-02', horas_consumidas: 3 },
      { fecha_inicio: '2026-10-03', fecha_fin: '2026-10-03', horas_consumidas: 6 },
    ]
    // Totals [2, 5, 11] have OLS slope 4.5; forecast starts at the last total, 11.
    expect(projectForecast(projectHours(plan, rows), rows, plan.fecha_fin).values).toEqual([null, null, 11, 15.5, 20])
  })
  it('does not invent a regression for empty or single-day data, or past the planned end', () => {
    for (const rows of [[], [{ fecha_inicio: plan.fecha_inicio, fecha_fin: plan.fecha_inicio, horas_consumidas: 5 }],
      [{ fecha_inicio: plan.fecha_inicio, fecha_fin: plan.fecha_fin, horas_consumidas: 25 }]]) {
      expect(projectForecast(projectHours(plan, rows), rows, plan.fecha_fin).values.every(v => v === null)).toBe(true)
    }
  })
  it('ends the actual path at the last recorded date and labels future values as projected', async () => {
    const wrapper = mount(ProjectHoursChart, { props: { project: plan, consumptions: [
      { fecha_inicio: '2026-10-01', fecha_fin: '2026-10-03', horas_consumidas: 30 },
    ] } })
    expect(wrapper.get('.actual-line').attributes('d')!.match(/L/g)).toHaveLength(2)
    expect(wrapper.get('.forecast-line').attributes('d')!.match(/L/g)).toHaveLength(2)
    expect(wrapper.get('.chart-values').text()).toContain('Proyectadas: 50 h')
    await wrapper.get('input').setValue(2)
    expect(wrapper.get('.chart-values').text()).toContain('Aplicadas: 30 h')
    wrapper.unmount()
  })
})


describe('forecast status', () => {
  it.each([
    [84.99, 'Falta de Recursos', 'forecast-warning'],
    [85, 'Aceptable', 'forecast-ok'],
    [100, 'Aceptable', 'forecast-ok'],
    [115, 'Aceptable', 'forecast-ok'],
    [115.01, 'Sobre aplicacion', 'forecast-warning'],
  ])('classifies a final forecast of %s hours', async (final, text, css) => {
    const wrapper = mount(ProjectHoursChart, { props: {
      project: { fecha_inicio: '2026-10-01', fecha_fin: '2026-10-05', horas_requeridas: 100 },
      consumptions: [{ fecha_inicio: '2026-10-01', fecha_fin: '2026-10-02', horas_consumidas: final * 2 / 5 }],
    } })
    expect(wrapper.get('.forecast-status').text()).toContain(text)
    expect(wrapper.get('.forecast-status').classes()).toContain(css)
    expect(wrapper.get('.forecast-line').attributes('style')).toContain(css === 'forecast-ok' ? 'rgb(21, 128, 61)' : 'rgb(185, 28, 28)')
    await wrapper.get('input').setValue(0)
    expect(wrapper.get('.forecast-status').text()).toContain(text)
    wrapper.unmount()
  })
  it('does not classify when a forecast cannot be calculated', () => {
    const wrapper = mount(ProjectHoursChart, { props: { project, consumptions: [] } })
    expect(wrapper.find('.forecast-status').exists()).toBe(false)
    wrapper.unmount()
  })
})

describe('forecast status and projected end date', () => {
  const plan = { fecha_inicio: '2026-10-01', fecha_fin: '2026-10-10', horas_requeridas: 100 }
  const row = (from: string, to: string, hours: number) => ({ fecha_inicio: from, fecha_fin: to, horas_consumidas: hours })
  it('classifies the projection with a 15 % tolerance', () => {
    expect(forecastStatus(null, 100)).toBeNull()
    expect(forecastStatus(115, 100)).toEqual({ text: 'Aceptable', acceptable: true })
    expect(forecastStatus(116, 100)?.text).toBe('Sobre aplicacion')
    expect(forecastStatus(84, 100)?.text).toBe('Falta de Recursos')
  })
  it('extends the regression line from the last recorded day', () => {
    const rows = [row('2026-10-01', '2026-10-03', 30)] // 10 h/day, 30 h after day 3 -> 100 h on Oct 10
    expect(projectForecast(projectHours(plan, rows), rows, plan.fecha_fin).slope).toBeCloseTo(10)
    expect(projectedEndDate(projectHours(plan, rows), rows, 100)).toBe('2026-10-10')
  })
  it('still projects a date for an overdue project and returns the real day once reached', () => {
    const overdue = [row('2026-10-01', '2026-10-12', 60)]
    expect(projectedEndDate(projectHours(plan, overdue), overdue, 100)).toBe('2026-10-20')
    const done = [row('2026-10-01', '2026-10-02', 100)]
    expect(projectedEndDate(projectHours(plan, done), done, 100)).toBe('2026-10-02')
  })
  it('has no date without a usable trend', () => {
    const one = [row('2026-10-01', '2026-10-01', 5)]
    expect(projectedEndDate(projectHours(plan, one), one, 100)).toBeNull()
    expect(projectedEndDate(projectHours(plan, []), [], 100)).toBeNull()
  })
})
