<script setup lang="ts">
import { computed, ref, useId, watch } from 'vue'
import { projectHours, projectForecast, forecastStatus as forecastStatusOf, type HoursConsumption, type HoursProject } from '@/projectHours'
import { fmt } from '@/utils'

const props = defineProps<{ project: HoursProject; consumptions: HoursConsumption[] }>()
const points = computed(() => projectHours(props.project, props.consumptions))
const forecast = computed(() => projectForecast(points.value, props.consumptions, props.project.fecha_fin))
const lastActualIndex = computed(() => points.value.reduce((last, point, index) => point.date <= forecast.value.lastDate ? index : last, -1))
const lastActual = computed(() => points.value[lastActualIndex.value])
const hasForecast = computed(() => forecast.value.values.some(value => value !== null))
const finalForecast = computed(() => forecast.value.values[points.value.findIndex(point => point.date === props.project.fecha_fin)] ?? null)
const forecastStatus = computed(() => forecastStatusOf(finalForecast.value, props.project.horas_requeridas))
const forecastColor = computed(() => forecastStatus.value?.acceptable === false ? '#b91c1c' : '#15803d')
const projected = computed(() => forecast.value.values[selected.value] ?? null)
const isActual = computed(() => !!current.value && current.value.date <= forecast.value.lastDate)
const selected = ref(0)
watch(points, (rows) => { selected.value = Math.max(0, rows.length - 1) }, { immediate: true })
const current = computed(() => points.value[selected.value])
const clipId = useId()
const left = 68, right = 856, top = 24, bottom = 125
const x = (index: number) => points.value.length === 1 ? (left + right) / 2 : left + index * (right - left) / (points.value.length - 1)
const y = (hours: number) => bottom - hours / props.project.horas_requeridas * (bottom - top)
function path(key: 'planned' | 'actual' | 'forecast') {
  let started = false
  return points.value.map((point, index) => {
    const value = key === 'forecast' ? forecast.value.values[index] : key === 'actual' && point.date > forecast.value.lastDate ? null : point[key]
    if (value === null || value === undefined) return ''
    const command = started ? 'L' : 'M'
    started = true
    return `${command}${x(index)},${y(value)}`
  }).join(' ')
}
const ticks = computed(() => [...new Set(Array.from({ length: Math.min(6, points.value.length) }, (_, i) =>
  Math.round(i * (points.value.length - 1) / Math.max(1, Math.min(6, points.value.length) - 1))))])
const label = (value: string) => value.split('-').reverse().join('/')
const total = computed(() => props.consumptions.reduce((sum, row) => sum + row.horas_consumidas, 0))
const excess = computed(() => Math.max(0, total.value - props.project.horas_requeridas))
const beforeStart = computed(() => props.consumptions.some(row => row.fecha_inicio < props.project.fecha_inicio))
function inspect(event: MouseEvent) {
  const bounds = (event.currentTarget as SVGElement).getBoundingClientRect()
  const position = (event.clientX - bounds.left) / bounds.width * 900
  selected.value = Math.max(0, Math.min(points.value.length - 1, Math.round((position - left) / (right - left) * (points.value.length - 1))))
}
</script>

<template>
  <section class="panel hours-chart">
    <h2>Horas acumuladas</h2>
    <p class="muted">Plan y consumos al cierre de cada día. Las horas de cada consumo se reparten uniformemente entre sus fechas, ambas incluidas.</p>
    <p v-if="forecastStatus" class="forecast-status" :class="forecastStatus.acceptable ? 'forecast-ok' : 'forecast-warning'" role="status">
      <strong>{{ forecastStatus.text }}</strong>
      <span> · Proyección al cierre: {{ fmt(finalForecast) }} h / {{ fmt(project.horas_requeridas) }} h requeridas</span>
    </p>
    <div class="chart-legend">
      <span><i class="planned-key" /> Planificadas</span>
      <span><i class="actual-key" /> Aplicadas</span>
      <span v-if="hasForecast"><i class="forecast-key" :style="{ borderColor: forecastColor }" /> Proyección lineal</span>
    </div>
    <div class="chart-scroll">
      <svg viewBox="0 0 900 177.5" role="img" aria-label="Horas planificadas, aplicadas y proyectadas por fecha" @mousemove="inspect" @click="inspect">
        <defs><clipPath :id="clipId"><rect :x="left - 2" :y="top - 3" :width="right - left + 4" :height="bottom - top + 6" /></clipPath></defs>
        <g v-for="step in [0, 1, 2, 3, 4]" :key="step">
          <line :x1="left" :x2="right" :y1="y(project.horas_requeridas * step / 4)" :y2="y(project.horas_requeridas * step / 4)" class="gridline" />
          <text :x="left - 10" :y="y(project.horas_requeridas * step / 4) + 4" text-anchor="end">{{ fmt(project.horas_requeridas * step / 4) }}</text>
        </g>
        <text x="16" y="16">Horas</text>
        <text x="450" y="172" text-anchor="middle">Fechas</text>
        <g v-for="index in ticks" :key="index">
          <text :x="x(index)" y="148" text-anchor="middle">{{ label(points[index]!.date) }}</text>
        </g>
        <g :clip-path="`url(#${clipId})`">
          <path :d="path('planned')" class="planned-line" />
          <path :d="path('actual')" class="actual-line" />
          <circle v-if="lastActual && lastActual.actual <= project.horas_requeridas" :cx="x(lastActualIndex)" :cy="y(lastActual.actual)" r="4" fill="#c2410c" />
          <path v-if="hasForecast" :d="path('forecast')" class="forecast-line" :style="{ stroke: forecastColor }" />
          <line v-if="current" :x1="x(selected)" :x2="x(selected)" :y1="top" :y2="bottom" class="cursor-line" />
          <circle v-if="current" :cx="x(selected)" :cy="y(current.planned)" r="4" fill="#2563eb" />
          <circle v-if="current && isActual && current.actual <= project.horas_requeridas" :cx="x(selected)" :cy="y(current.actual)" r="4" fill="#c2410c" />
        </g>
          <circle v-if="!isActual && projected !== null && projected <= project.horas_requeridas" :cx="x(selected)" :cy="y(projected)" r="4" :fill="forecastColor" />
      </svg>
    </div>
    <label class="day-selector">Consultar día
      <input v-model.number="selected" type="range" min="0" :max="Math.max(0, points.length - 1)" step="1" :disabled="points.length < 2" />
    </label>
    <p v-if="current" class="chart-values" aria-live="polite">
      <strong>{{ label(current.date) }}</strong> · Planificadas: {{ fmt(current.planned) }} h
      <template v-if="isActual"> · Aplicadas: {{ fmt(current.actual) }} h</template>
      <template v-else-if="projected !== null"> · Proyectadas: {{ fmt(projected) }} h</template>
      <template v-else> · Sin datos para proyectar</template>
    </p>
    <p v-if="hasForecast" class="muted">Proyección estimada con la pendiente de regresión lineal de los acumulados diarios, continuando desde el último valor aplicado. No representa horas registradas.</p>
    <p v-else-if="consumptions.length && forecast.lastDate < project.fecha_fin" class="muted">Se necesitan al menos dos días de datos dentro del proyecto para calcular la regresión.</p>
    <p v-if="hasForecast && (forecast.values.at(-1) ?? 0) > project.horas_requeridas" class="overrun">La proyección al fin del proyecto es {{ fmt(forecast.values.at(-1)) }} h y supera la escala del gráfico.</p>
    <p v-if="!consumptions.length" class="muted">Sin consumos registrados: las horas aplicadas son cero.</p>
    <p v-if="excess > 0" class="overrun">Total aplicado: {{ fmt(total) }} h. Exceso: {{ fmt(excess) }} h. El eje muestra hasta {{ fmt(project.horas_requeridas) }} h; los valores superiores quedan fuera del gráfico y se pueden consultar por día.</p>
    <p v-if="beforeStart" class="muted">El primer día incluye las horas aplicadas antes del inicio del proyecto.</p>
  </section>
</template>

<style scoped>
.forecast-ok { color: #15803d; }
.forecast-warning { color: #b91c1c; }
.hours-chart { margin-block: 1.5rem; }
.chart-legend { display: flex; flex-wrap: wrap; gap: 1.5rem; margin-bottom: 1rem; }
.chart-legend span { display: inline-flex; align-items: center; gap: .5rem; }
.chart-legend i { width: 26px; border-top: 3px solid; }
.planned-key { border-color: #2563eb !important; }
.actual-key { border-color: #c2410c !important; border-top-style: dashed !important; }

.chart-scroll { overflow-x: auto; }
svg { display: block; width: 100%; min-width: 560px; }
text { fill: #475569; font-size: 12px; }
.gridline { stroke: #e2e8f0; }
.planned-line, .actual-line, .forecast-line { fill: none; stroke-width: 3; stroke-linejoin: round; }
.planned-line { stroke: #2563eb; }
.actual-line { stroke: #c2410c; stroke-dasharray: 7 4; }
.forecast-line { stroke: #15803d; }
.cursor-line { stroke: #94a3b8; stroke-dasharray: 3 4; }
.day-selector { display: flex; align-items: center; gap: 1rem; margin: .75rem 0; }
.day-selector input { flex: 1; min-width: 0; }
.chart-values { font-variant-numeric: tabular-nums; }
</style>
