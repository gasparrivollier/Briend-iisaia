<script setup lang="ts">
import { computed } from 'vue'
import StatGrid from '@/components/StatGrid.vue'
import { isoToLocal, type Report } from '@/dashboard'
import { fmt } from '@/utils'

const props = defineProps<{ report: Report }>()
const tasks = computed(() => props.report.tareas)
const stats = computed(() => [
  ['Tareas planificadas', String(tasks.value.total)],
  ['Completadas', String(tasks.value.completadas)],
  ['En curso', String(tasks.value.en_curso)],
  ['Sin recurso asignado', String(tasks.value.sin_recurso)],
] as [string, string][])
const lists = computed(() => [
  ['Tareas vencidas', 'Terminaron según el plan y no están al 100 %.', tasks.value.vencidas],
  ['Tareas atrasadas sin iniciar', 'Debían haber empezado y siguen en 0 %.', tasks.value.sin_iniciar_atrasadas],
] as const)
</script>

<template>
  <section class="dash-panel">
    <h2>Salud de las tareas</h2>
    <p v-if="!tasks.total" class="muted">Este proyecto no tiene tareas planificadas en el Gantt.</p>
    <template v-else>
      <StatGrid :items="stats" />
      <div class="panel">
        <div class="progress-label"><span>Avance planificado a hoy</span><strong>{{ fmt(tasks.avance_planificado) }} %</strong></div>
        <div class="progress" role="progressbar" aria-label="Avance planificado" :aria-valuenow="tasks.avance_planificado" aria-valuemin="0" aria-valuemax="100"><div class="progress-bar plan-bar" :style="{ width: tasks.avance_planificado + '%' }"></div></div>
        <div class="progress-label"><span>Avance real de las tareas</span><strong>{{ fmt(tasks.avance_real) }} %</strong></div>
        <div class="progress" role="progressbar" aria-label="Avance real de las tareas" :aria-valuenow="tasks.avance_real" aria-valuemin="0" aria-valuemax="100"><div class="progress-bar" :style="{ width: tasks.avance_real + '%' }"></div></div>
        <p class="muted task-note">Ponderado por la duración de cada tarea.</p>
      </div>
      <div class="summary-grid">
        <section v-for="[title, hint, rows] in lists" :key="title" class="panel">
          <h3>{{ title }} ({{ rows.length }})</h3>
          <p class="muted">{{ hint }}</p>
          <div v-if="rows.length" class="table-responsive">
            <table class="table">
              <thead><tr><th>Tarea</th><th>Fechas</th><th>Avance</th><th>Recurso</th></tr></thead>
              <tbody>
                <tr v-for="row in rows" :key="row.tarea_id">
                  <td><RouterLink :to="`/tareas/${row.tarea_id}/editar`">{{ row.tarea_nombre }}</RouterLink></td>
                  <td class="date-cell">{{ isoToLocal(row.fecha_inicio) }} → {{ isoToLocal(row.fecha_fin) }}</td>
                  <td>{{ fmt(row.porcentaje_avance) }} %</td>
                  <td>{{ row.recurso_nombre ?? 'Sin asignar' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p v-else class="muted">Ninguna. 👍</p>
        </section>
      </div>
    </template>
  </section>
</template>
