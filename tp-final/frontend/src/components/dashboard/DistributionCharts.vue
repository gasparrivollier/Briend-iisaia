<script setup lang="ts">
import { computed } from 'vue'
import { shareBars, type Report } from '@/dashboard'
import BarChart from './BarChart.vue'

const props = defineProps<{ report: Report }>()
const charts = computed(() =>
  ([
    ['Horas por recurso', props.report.distribucion.por_recurso],
    ['Horas por rol', props.report.distribucion.por_rol],
    ['Horas por actividad', props.report.distribucion.actividades],
  ] as const).map(([title, shares]) => ({ title, shares, ...shareBars([...shares], title) })),
)
</script>

<template>
  <section class="dash-panel">
    <h2>Distribución de horas</h2>
    <div class="distribution-grid">
      <section v-for="chart in charts" :key="chart.title" class="panel">
        <h3>{{ chart.title }}</h3>
        <BarChart v-if="chart.shares.length" :data="chart.data" :label="chart.title" :notes="chart.notes" horizontal />
        <p v-else class="muted">Sin horas registradas.</p>
      </section>
    </div>
  </section>
</template>
