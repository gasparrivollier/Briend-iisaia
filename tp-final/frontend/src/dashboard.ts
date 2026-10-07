// Pure helpers that shape the report API output for the dashboard (no canvas, easy to test).
import type { ChartData } from 'chart.js'
import type { Schemas } from '@/api/client'
import { fmt } from '@/utils'

export type Report = Schemas['ProyectoReporte']
export type Period = Schemas['ReportePeriodo']
export type Share = Schemas['ReporteParte']
export type Health = Schemas['ReporteSalud']

// Categorical slots 1-5 of the reference palette (validated adjacent-pair set); the rest folds into "Otros".
export const SERIES_COLORS = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4']
export const OTHER_COLOR = '#9aa7aa'
export const OTHER_LABEL = 'Otros'
export const SURFACE = '#ffffff'

/** '2026-10-05' -> '05/10/2026' */
export const isoToLocal = (iso: string | null | undefined) => (iso ? iso.split('-').reverse().join('/') : '—')

export function periodLabel(period: Period, kind: 'semana' | 'mes') {
  const [year, month, day] = period.desde.split('-')
  return kind === 'mes' ? `${month}/${year}` : `${day}/${month}`
}

/** Stacked bars of hours per period; the largest five names keep their own color, the rest is "Otros". */
export function stackedHours(periods: Period[], kind: 'semana' | 'mes', by: 'por_rol' | 'por_recurso'): ChartData<'bar'> {
  const totals = new Map<string, number>()
  for (const period of periods) {
    for (const [name, hours] of Object.entries(period[by])) totals.set(name, (totals.get(name) ?? 0) + hours)
  }
  const ranked = [...totals].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).map(([name]) => name)
  const kept = ranked.slice(0, SERIES_COLORS.length)
  const datasets = kept.map((name, index) => ({
    label: name,
    data: periods.map((period) => period[by][name] ?? 0),
    backgroundColor: SERIES_COLORS[index]!,
  }))
  if (ranked.length > kept.length) {
    datasets.push({
      label: OTHER_LABEL,
      data: periods.map((period) => ranked.slice(kept.length).reduce((sum, name) => sum + (period[by][name] ?? 0), 0)),
      backgroundColor: OTHER_COLOR,
    })
  }
  return {
    labels: periods.map((period) => periodLabel(period, kind)),
    datasets: datasets.map((dataset) => ({ ...dataset, borderColor: SURFACE, borderWidth: 2 })),
  }
}

/** One horizontal bar per name (already sorted by the API). */
export function shareBars(shares: Share[], label: string): { data: ChartData<'bar'>; notes: string[] } {
  return {
    data: {
      labels: shares.map((share) => share.nombre),
      datasets: [{ label, data: shares.map((share) => share.horas), backgroundColor: SERIES_COLORS[0]! }],
    },
    notes: shares.map((share) => `${fmt(share.porcentaje)} % del total`),
  }
}

export type IndexView = { title: string; value: string; state: 'bien' | 'atencion' | 'critico' | null; sentence: string }

const STATE_TEXT = { bien: 'En orden', atencion: 'Atención', critico: 'Crítico' } as const
export const stateText = (state: IndexView['state']) => (state ? STATE_TEXT[state] : 'Sin datos')

export function indexViews(health: Health): IndexView[] {
  const index = (value: number | null) => (value === null ? '—' : fmt(value))
  return [
    {
      title: 'Eficiencia de horas',
      value: index(health.indice_eficiencia),
      state: health.estado_eficiencia,
      sentence:
        health.indice_eficiencia === null
          ? 'Todavía no hay horas consumidas.'
          : `Se consumió el ${fmt(health.porcentaje_consumo)} % de las horas y el avance es del ${fmt(health.porcentaje_avance)} %.`,
    },
    {
      title: 'Cumplimiento del cronograma',
      value: index(health.indice_cronograma),
      state: health.estado_cronograma,
      sentence:
        health.indice_cronograma === null
          ? 'El proyecto todavía no empezó.'
          : `Pasó el ${fmt(health.porcentaje_tiempo)} % del tiempo y el avance es del ${fmt(health.porcentaje_avance)} %.`,
    },
  ]
}

/** Gap between the projected and planned end, in plain words. */
export function endGap(projected: string | null, planned: string): string | null {
  if (!projected) return null
  const days = Math.round((Date.parse(projected) - Date.parse(planned)) / 86400000)
  if (days === 0) return 'justo en la fecha de fin planificada'
  return `${Math.abs(days)} día${Math.abs(days) === 1 ? '' : 's'} ${days > 0 ? 'después' : 'antes'} del fin planificado`
}

export function startGap(days: number | null): string {
  if (days === null) return '—'
  if (days === 0) return 'A tiempo'
  return `${Math.abs(days)} día${Math.abs(days) === 1 ? '' : 's'} ${days > 0 ? 'tarde' : 'antes'}`
}
