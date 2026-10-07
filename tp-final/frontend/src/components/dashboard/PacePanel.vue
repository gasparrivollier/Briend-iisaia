<script setup lang="ts">
import { computed } from 'vue'
import StatGrid from '@/components/StatGrid.vue'
import ProjectHoursChart from '@/components/ProjectHoursChart.vue'
import { endGap, isoToLocal, type Report } from '@/dashboard'
import { projectHours, projectedEndDate, type HoursConsumption } from '@/projectHours'
import { fmt } from '@/utils'

const props = defineProps<{ report: Report; consumptions: HoursConsumption[] }>()
const pace = computed(() => props.report.ritmo)
const endDate = computed(() =>
  projectedEndDate(projectHours(props.report.proyecto, props.consumptions), props.consumptions, props.report.proyecto.horas_requeridas),
)
const stats = computed(() => [
  ['Ritmo últimas 4 semanas', `${fmt(pace.value.horas_semana_reciente)} h/sem`],
  ['Ritmo promedio histórico', `${fmt(pace.value.horas_semana_promedio)} h/sem`],
  ['Ritmo necesario para terminar', pace.value.horas_semana_necesarias === null ? '—' : `${fmt(pace.value.horas_semana_necesarias)} h/sem`],
  ['Proyección por regresión: horas agotadas', isoToLocal(endDate.value)],
] as [string, string][])
const gap = computed(() => endGap(endDate.value, props.report.proyecto.fecha_fin))
</script>

<template>
  <section class="dash-panel">
    <h2>Ritmo y proyección</h2>
    <StatGrid :items="stats" />
    <p v-if="pace.horas_semana_necesarias === null && report.proyecto.saldo > 0" class="overrun">El plazo del proyecto venció y todavía hay saldo de horas.</p>
    <p v-else-if="report.proyecto.saldo <= 0" class="muted">Ya se consumieron todas las horas requeridas.</p>
    <p v-else class="muted">Quedan {{ pace.dias_restantes }} días y {{ fmt(report.proyecto.saldo) }} h de saldo.</p>
    <p v-if="gap" class="muted">Al ritmo de la regresión lineal, las horas requeridas se completan {{ gap }}.</p>
    <p v-else class="muted">Se necesitan al menos dos días de consumos con tendencia creciente para proyectar la fecha.</p>
    <ProjectHoursChart :project="report.proyecto" :consumptions="consumptions" />
  </section>
</template>
