// Pure mapping between the API and frappe-gantt. frappe-gantt writes the bar label with innerHTML,
// so `name` is HTML-escaped here; the unescaped text travels in `raw_name` and the popup renders it
// with textContent (escaping it again would show "R&amp;D").
import type { GanttTask, PopupContext } from 'frappe-gantt'
import type { Task } from '@/api/client'
import { fmt } from '@/utils'

export type Bar = GanttTask & { ref_id: number; raw_name: string; details: string }

const ESCAPES: Record<string, string> = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }

export const escapeHtml = (text: string) => text.replace(/[&<>"']/g, (char) => ESCAPES[char]!)

/**
 * Local calendar date as YYYY-MM-DD. frappe-gantt builds local dates (and reports an inclusive end
 * as 23:59:59 of the last day), so `toISOString()` would shift dates in UTC-3.
 */
export function toISODate(date: Date): string {
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

/** One bar per task. Finished tasks and overdue unfinished ones get their own color. */
export function taskBars(tasks: Task[], today = toISODate(new Date())): Bar[] {
  return tasks.map((t) => {
    const progress = Math.max(0, Math.min(100, t.porcentaje_avance))
    const late = progress < 100 && t.fecha_fin < today
    return {
      id: `tarea-${t.tarea_id}`, // frappe-gantt uses it in CSS class selectors: must not start with a digit
      ref_id: t.tarea_id,
      name: escapeHtml(t.tarea_nombre),
      raw_name: t.tarea_nombre,
      start: t.fecha_inicio,
      end: t.fecha_fin,
      progress,
      custom_class: progress >= 100 ? 'gantt-done' : late ? 'gantt-late' : 'gantt-open',
      details:
        `${t.recurso_nombre ?? 'Sin asignar'} · ${t.fecha_inicio} → ${t.fecha_fin} · ` +
        `Avance ${fmt(t.porcentaje_avance)} %${late ? ' · Atrasada' : ''}`,
    }
  })
}

/** Popup that never goes through innerHTML. */
export function popup(ctx: PopupContext) {
  const bar = ctx.task as Bar
  ctx.get_title().textContent = bar.raw_name
  ctx.get_subtitle().textContent = ''
  ctx.get_details().textContent = bar.details
}
