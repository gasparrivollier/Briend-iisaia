<script setup lang="ts">
// The only place that knows about frappe-gantt, so the library can be swapped without touching pages.
import Gantt, { type GanttTask, type ViewMode } from 'frappe-gantt'
import 'frappe-gantt.css'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { popup, toISODate, type Bar } from '@/gantt'

const props = withDefaults(defineProps<{ bars: Bar[]; readonly?: boolean }>(), { readonly: true })
const emit = defineEmits<{
  open: [id: number]
  move: [id: number, start: string, end: string]
  progress: [id: number, progress: number]
}>()

const VIEWS: [ViewMode, string][] = [['Day', 'Día'], ['Week', 'Semana'], ['Month', 'Mes']]
const view = ref<ViewMode>('Week')
const host = ref<HTMLElement>()
let chart: Gantt | undefined

const refId = (task: GanttTask) => (task as Bar).ref_id

// frappe-gantt fires date_change on every mousemove step that crosses a day, not once per drag.
// Keep the last dates per bar and emit when the mouse is released (document mouseup runs after
// frappe's own handler on the SVG), so a drag is one `move` = one request.
const pending = new Map<number, [string, string]>()
function flushMoves() {
  for (const [id, [start, end]] of pending) emit('move', id, start, end)
  pending.clear()
}

/**
 * The chart is built once per mount: frappe-gantt binds a `document` mouseup listener in its
 * constructor and never removes it, so rebuilding on every data change would leak charts. Updates
 * go through setup_tasks + change_view_mode(…, true), i.e. `refresh()` without scrolling back to today.
 */
function render() {
  if (!host.value || !props.bars.length) return // frappe-gantt cannot draw zero tasks
  const tasks = props.bars.map((bar) => ({ ...bar })) // it mutates tasks (_start, _end, _index)
  const first = tasks.reduce((min, t) => (t.start < min ? t.start : min), tasks[0]!.start)
  if (chart) {
    chart.options.readonly = props.readonly // read by the bars on each interaction
    chart.options.scroll_to = first // used when the scale changes
    chart.setup_tasks(tasks)
    chart.change_view_mode(view.value, true)
    return
  }
  chart = new Gantt(host.value, tasks, {
    view_mode: view.value,
    language: 'es',
    readonly: props.readonly,
    move_dependencies: false, // a drag moves only its own bar (dependencies are not enforced)
    infinite_padding: false,
    scroll_to: first, // open on the plan, not on the padding before it
    today_button: false, // its label is not translated
    popup_on: 'hover',
    popup,
    // A click also fires after a drag, so opening the task is on double click.
    on_double_click: (task) => emit('open', refId(task)),
    on_date_change: (task, start, end) => pending.set(refId(task), [toISODate(start), toISODate(end)]),
    on_progress_change: (task, progress) => emit('progress', refId(task), Math.round(progress)),
  })
}

onMounted(() => {
  document.addEventListener('mouseup', flushMoves)
  render()
})
watch(() => [props.bars, props.readonly], render, { flush: 'post' }) // after v-show reveals the host
watch(view, (mode) => chart?.change_view_mode(mode))
onBeforeUnmount(() => {
  document.removeEventListener('mouseup', flushMoves)
  pending.clear()
  chart = undefined
  host.value?.replaceChildren()
})

/** Redraw from the props, e.g. to undo a drag the API rejected (the data itself did not change). */
defineExpose({ reset: render })
</script>

<template>
  <div class="gantt-panel">
    <div class="gantt-views" role="group" aria-label="Escala del diagrama">
      <button
        v-for="[mode, label] in VIEWS" :key="mode" type="button"
        :class="['btn', 'btn-sm', mode === view ? 'btn-dark' : 'btn-outline-secondary']"
        :aria-pressed="mode === view" @click="view = mode"
      >{{ label }}</button>
    </div>
    <div v-show="bars.length" ref="host" class="gantt-host" data-testid="gantt"></div>
    <p v-if="!bars.length" class="muted">Todavía no hay tareas planificadas.</p>
  </div>
</template>
