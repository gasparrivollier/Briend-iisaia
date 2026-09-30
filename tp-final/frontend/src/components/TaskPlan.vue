<script setup lang="ts">
// "Planificación" section of a project: its tasks as a Gantt (draggable for the owner/admin) + table.
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, type Task } from '@/api/client'
import DeleteButton from '@/components/DeleteButton.vue'
import ProjectGantt from '@/components/ProjectGantt.vue'
import { handleError, showNotice } from '@/composables/notice'
import { taskBars } from '@/gantt'
import { fmt } from '@/utils'

const props = defineProps<{ projectId: number; editable: boolean }>()
const router = useRouter()
const queryClient = useQueryClient()
const tasks = useQuery({ queryKey: ['tareas', () => props.projectId], queryFn: () => api.tasks(props.projectId) })
const bars = computed(() => taskBars(tasks.data.value ?? []))
const gantt = ref<InstanceType<typeof ProjectGantt>>()

/** Drag on the chart: one PUT with the task's other fields unchanged. A rejected change is undone. */
async function save(id: number, changes: Partial<Task>, message: string) {
  const task = tasks.data.value?.find((t) => t.tarea_id === id)
  if (!task) return
  const { tarea_nombre, fecha_inicio, fecha_fin, porcentaje_avance, recurso_id } = { ...task, ...changes }
  try {
    await api.updateTask(id, { tarea_nombre, fecha_inicio, fecha_fin, porcentaje_avance, recurso_id })
    showNotice(message, 'success')
  } catch (error) {
    gantt.value?.reset()
    await handleError(error, router)
  }
  await queryClient.invalidateQueries({ queryKey: ['tareas'] })
}

const move = (id: number, fecha_inicio: string, fecha_fin: string) =>
  save(id, { fecha_inicio, fecha_fin }, `Tarea reprogramada: ${fecha_inicio} → ${fecha_fin}.`)
const progress = (id: number, porcentaje_avance: number) =>
  save(id, { porcentaje_avance }, `Avance de la tarea: ${porcentaje_avance} %.`)
function open(id: number) {
  if (props.editable) void router.push(`/tareas/${id}/editar`)
}
</script>

<template>
  <section class="panel plan">
    <div class="section-heading">
      <h2>Planificación</h2>
      <RouterLink v-if="editable" class="btn btn-primary" :to="`/proyectos/${projectId}/tareas/nueva`">+ Nueva tarea</RouterLink>
    </div>
    <p v-if="tasks.isPending.value" role="status">Cargando…</p>
    <p v-else-if="tasks.error.value" class="overrun">{{ tasks.error.value.message }}</p>
    <template v-else>
      <ProjectGantt ref="gantt" :bars="bars" :readonly="!editable" @move="move" @progress="progress" @open="open" />
      <p v-if="bars.length" class="muted gantt-legend">
        Verde: en curso · Azul: terminada · Rojo: atrasada (vencida sin llegar al 100 %).
        <template v-if="editable">Arrastrá una barra para cambiar sus fechas o su borde de avance; doble clic para editarla.</template>
      </p>
      <div v-if="bars.length" class="table-responsive">
        <table class="table">
          <thead>
            <tr><th>Tarea / responsable</th><th>Período</th><th class="text-end">Avance</th><th>Acciones</th></tr>
          </thead>
          <tbody>
            <tr v-for="t in tasks.data.value" :key="t.tarea_id">
              <td><strong>{{ t.tarea_nombre }}</strong><small class="d-block muted">{{ t.recurso_nombre ?? 'Sin asignar' }}</small></td>
              <td class="date-cell">{{ t.fecha_inicio }}<br />{{ t.fecha_fin }}</td>
              <td class="text-end">{{ fmt(t.porcentaje_avance) }} %</td>
              <td>
                <div v-if="editable" class="actions">
                  <RouterLink class="btn btn-sm btn-outline-secondary" :to="`/tareas/${t.tarea_id}/editar`">Editar</RouterLink>
                  <DeleteButton :remove="() => api.deleteTask(t.tarea_id)" :return-to="`/proyectos/${projectId}`" />
                </div>
                <span v-else class="muted">Solo lectura</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </section>
</template>
