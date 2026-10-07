import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import {
  OTHER_COLOR,
  SERIES_COLORS,
  endGap,
  indexViews,
  isoToLocal,
  periodLabel,
  shareBars,
  stackedHours,
  startGap,
  type Health,
  type Period,
} from '@/dashboard'
import { routes } from '@/router'
import HealthPanel from '@/components/dashboard/HealthPanel.vue'

const period = (desde: string, porRol: Record<string, number>): Period => ({
  desde,
  hasta: desde,
  horas: Object.values(porRol).reduce((a, b) => a + b, 0),
  por_rol: porRol,
  por_recurso: {},
})

describe('dashboard data shaping', () => {
  it('formats dates and period labels', () => {
    expect(isoToLocal('2026-10-05')).toBe('05/10/2026')
    expect(isoToLocal(null)).toBe('—')
    expect(periodLabel(period('2026-10-05', {}), 'semana')).toBe('05/10')
    expect(periodLabel(period('2026-10-01', {}), 'mes')).toBe('10/2026')
  })
  it('stacks the five biggest names and folds the rest into Otros', () => {
    const rows = [
      period('2026-10-05', { a: 10, b: 9, c: 8, d: 7, e: 6, f: 2, g: 1 }),
      period('2026-10-12', { a: 1, f: 3 }),
    ]
    const data = stackedHours(rows, 'semana', 'por_rol')
    expect(data.datasets.map((d) => d.label)).toEqual(['a', 'b', 'c', 'd', 'e', 'Otros'])
    expect(data.datasets.map((d) => d.backgroundColor).slice(0, 5)).toEqual(SERIES_COLORS)
    const others = data.datasets.at(-1)!
    expect(others.backgroundColor).toBe(OTHER_COLOR)
    expect(others.data).toEqual([3, 3])
    expect(data.labels).toEqual(['05/10', '12/10'])
  })
  it('keeps all names when there are five or fewer', () => {
    const data = stackedHours([period('2026-10-05', { a: 1, b: 2 })], 'semana', 'por_rol')
    expect(data.datasets.map((d) => d.label)).toEqual(['b', 'a'])
  })
  it('builds horizontal bars with a note per category', () => {
    const { data, notes } = shareBars([{ nombre: 'ana', horas: 3, porcentaje: 75 }, { nombre: 'bruno', horas: 1, porcentaje: 25 }], 'Horas')
    expect(data.labels).toEqual(['ana', 'bruno'])
    expect(notes).toEqual(['75 % del total', '25 % del total'])
  })
  it('describes the gaps in plain words', () => {
    expect(endGap(null, '2026-10-10')).toBeNull()
    expect(endGap('2026-10-10', '2026-10-10')).toBe('justo en la fecha de fin planificada')
    expect(endGap('2026-10-13', '2026-10-10')).toBe('3 días después del fin planificado')
    expect(endGap('2026-10-09', '2026-10-10')).toBe('1 día antes del fin planificado')
    expect(startGap(null)).toBe('—')
    expect(startGap(0)).toBe('A tiempo')
    expect(startGap(2)).toBe('2 días tarde')
    expect(startGap(-1)).toBe('1 día antes')
  })
})

const health: Health = {
  porcentaje_tiempo: 50,
  porcentaje_consumo: 60,
  porcentaje_avance: 40,
  horas_ganadas: 4,
  indice_eficiencia: 0.67,
  estado_eficiencia: 'critico',
  indice_cronograma: null,
  estado_cronograma: null,
}

describe('health panel', () => {
  it('explains each index and never relies on color alone', () => {
    const [efficiency, schedule] = indexViews(health)
    expect(efficiency!.sentence).toBe('Se consumió el 60 % de las horas y el avance es del 40 %.')
    expect(schedule!.sentence).toBe('El proyecto todavía no empezó.')
    const wrapper = mount(HealthPanel, { props: { health } })
    expect(wrapper.text()).toContain('Crítico')
    expect(wrapper.text()).toContain('Sin datos')
    expect(wrapper.findAll('[role="progressbar"]')).toHaveLength(3)
  })
})

describe('dashboard route', () => {
  it('resolves /proyectos/:id/dashboard with a numeric id', () => {
    const router = createRouter({ history: createMemoryHistory(), routes })
    const resolved = router.resolve('/proyectos/7/dashboard')
    expect(resolved.name).toBe('project-dashboard')
    expect(routes.find((r) => r.name === 'project-dashboard')!.props).toBeTypeOf('function')
    expect(router.resolve('/proyectos/x/dashboard').name).toBe('not-found')
  })
})
