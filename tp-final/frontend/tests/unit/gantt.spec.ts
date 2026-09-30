import { describe, expect, it } from 'vitest'
import type { PopupContext } from 'frappe-gantt'
import type { Task } from '@/api/client'
import { escapeHtml, popup, taskBars, toISODate } from '@/gantt'

const task = (over: Partial<Task> = {}): Task => ({
  tarea_id: 7,
  proyecto_id: 1,
  tarea_nombre: 'R&D <img src=x onerror=alert(1)>',
  fecha_inicio: '2026-03-01',
  fecha_fin: '2026-03-31',
  porcentaje_avance: 40,
  recurso_id: 2,
  recurso_nombre: 'Ana',
  ...over,
})
const TODAY = '2026-03-15'

describe('gantt mapping', () => {
  it('runs in a negative UTC offset (where toISOString would shift dates)', () => {
    expect(new Date(2026, 0, 1).getTimezoneOffset()).toBe(180) // npm test sets TZ=America/Argentina/Buenos_Aires
  })

  it('escapes the bar label but keeps the raw name for the popup', () => {
    const [bar] = taskBars([task()], TODAY)
    expect(bar!.name).toBe('R&amp;D &lt;img src=x onerror=alert(1)&gt;')
    expect(bar!.raw_name).toBe('R&D <img src=x onerror=alert(1)>')
    expect(escapeHtml(`"'`)).toBe('&quot;&#39;')
  })

  it('renders the popup as text, escaped exactly once', () => {
    const [bar] = taskBars([task()], TODAY)
    const [title, subtitle, details] = [0, 1, 2].map(() => document.createElement('div'))
    popup({ task: bar!, get_title: () => title!, get_subtitle: () => subtitle!, get_details: () => details! } as PopupContext)
    expect(title!.textContent).toBe('R&D <img src=x onerror=alert(1)>')
    expect(title!.querySelector('img')).toBeNull()
    expect(title!.innerHTML).toContain('R&amp;D')
    expect(title!.innerHTML).not.toContain('&amp;amp;')
    expect(details!.textContent).toBe('Ana · 2026-03-01 → 2026-03-31 · Avance 40 %')
  })

  it('keeps inclusive API dates, a selector-safe id and the numeric id', () => {
    const [bar] = taskBars([task({ recurso_nombre: null })], TODAY)
    expect([bar!.start, bar!.end, bar!.id, bar!.ref_id]).toEqual(['2026-03-01', '2026-03-31', 'tarea-7', 7])
    expect(bar!.details).toMatch(/^Sin asignar · /)
  })

  it('classifies open, done and late tasks', () => {
    const [open, done, late, doneLate, clamped] = taskBars(
      [
        task(),
        task({ porcentaje_avance: 100 }),
        task({ fecha_fin: '2026-03-14' }),
        task({ fecha_fin: '2026-03-14', porcentaje_avance: 100 }),
        task({ porcentaje_avance: 140 }),
      ],
      TODAY,
    )
    expect([open, done, late, doneLate].map((b) => b!.custom_class)).toEqual(['gantt-open', 'gantt-done', 'gantt-late', 'gantt-done'])
    expect(late!.details).toMatch(/Atrasada$/)
    expect(taskBars([task({ fecha_fin: TODAY })], TODAY)[0]!.custom_class).toBe('gantt-open') // due today is not late
    expect(clamped!.progress).toBe(100)
  })

  it('formats dates back as the local calendar day', () => {
    // frappe-gantt reports an inclusive end as 23:59:59 local of the last day.
    const end = new Date(2026, 2, 31, 23, 59, 59)
    expect(end.toISOString().slice(0, 10)).toBe('2026-04-01') // the bug this guards against
    expect(toISODate(end)).toBe('2026-03-31')
    expect(toISODate(new Date(2026, 2, 1))).toBe('2026-03-01')
  })
})
