<script setup lang="ts">
import { computed } from 'vue'
import StatGrid from '@/components/StatGrid.vue'
import { isoToLocal, startGap, type Report } from '@/dashboard'
import { fmt } from '@/utils'

const props = defineProps<{ report: Report }>()
const run = computed(() => props.report.ejecucion)
const stats = computed(() => [
  ['Primer consumo (plan: ' + isoToLocal(props.report.proyecto.fecha_inicio) + ')', isoToLocal(run.value.primer_consumo)],
  ['Desvío de inicio', startGap(run.value.dias_desvio_inicio)],
  ['Días con actividad', `${run.value.dias_con_actividad} / ${run.value.dias_transcurridos}`],
  ['Horas fuera del plazo', fmt(run.value.horas_antes_inicio + run.value.horas_despues_fin) + ' h'],
] as [string, string][])
</script>

<template>
  <section class="dash-panel">
    <h2>Ejecución real vs. plan</h2>
    <StatGrid :items="stats" />
    <p v-if="run.horas_antes_inicio > 0" class="muted">{{ fmt(run.horas_antes_inicio) }} h se aplicaron antes del inicio planificado.</p>
    <p v-if="run.horas_despues_fin > 0" class="overrun">{{ fmt(run.horas_despues_fin) }} h se aplicaron después de la fecha de fin planificada.</p>
    <p v-if="!run.primer_consumo" class="muted">Sin consumos registrados.</p>
    <p v-else class="muted">Último consumo: {{ isoToLocal(run.ultimo_consumo) }} (fin planificado: {{ isoToLocal(report.proyecto.fecha_fin) }}).</p>
  </section>
</template>
