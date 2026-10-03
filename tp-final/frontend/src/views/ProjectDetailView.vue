<script setup lang="ts">
import { useQuery } from '@tanstack/vue-query'
import { computed } from 'vue'
import { api } from '@/api/client'
import ConsumptionTable from '@/components/ConsumptionTable.vue'
import DeleteButton from '@/components/DeleteButton.vue'
import LoadState from '@/components/LoadState.vue'
import PageHeading from '@/components/PageHeading.vue'
import StatGrid from '@/components/StatGrid.vue'
import TaskPlan from '@/components/TaskPlan.vue'
import ProjectHoursChart from '@/components/ProjectHoursChart.vue'
import { useSessionStore } from '@/stores/session'
import { fmt } from '@/utils'

const props = defineProps<{ id: number }>()
const session = useSessionStore()
const detail = useQuery({ queryKey: ['proyecto', () => props.id], queryFn: () => api.project(props.id) })

const project = computed(() => detail.data.value?.proyecto)
const editable = computed(
  () => !!session.user && (session.user.es_admin || session.user.recurso_id === project.value?.owner_id),
)
const stats = computed(() => {
  const p = project.value
  if (!p) return []
  return [
    ['Horas requeridas', fmt(p.horas_requeridas)],
    [`Horas consumidas · ${fmt(p.porcentaje_consumo)} %`, fmt(p.horas_consumidas)],
    ['Saldo / exceso de horas', `${fmt(p.saldo)} / ${fmt(p.exceso)}`],
    ['Avance real (manual)', fmt(p.porcentaje_avance) + ' %'],
  ] as [string, string][]
})
const summaries = computed(() => [
  ['Horas por recurso', detail.data.value?.por_recurso ?? {}],
  ['Horas por rol', detail.data.value?.por_rol ?? {}],
] as [string, Record<string, number>][])
</script>

<template>
  <LoadState :loading="detail.isPending.value" :error="detail.error.value" @retry="detail.refetch()">
    <template v-if="project && session.user">
      <RouterLink to="/proyectos">← Proyectos</RouterLink>
      <PageHeading
        :title="project.proyecto_nombre"
        :subtitle="`${project.responsable} · ${project.fecha_inicio} → ${project.fecha_fin} · ${project.proyect_status}`"
        eyebrow="DETALLE DEL PROYECTO"
      >
        <div class="actions">
          <RouterLink v-if="editable" class="btn btn-outline-secondary" :to="`/proyectos/${id}/editar`">Editar proyecto</RouterLink>
          <DeleteButton v-if="session.user.es_admin" :remove="() => api.deleteProject(id)" return-to="/proyectos" />
        </div>
      </PageHeading>
      <StatGrid :items="stats" />
      <TaskPlan :project-id="id" :editable="editable" />
      <ProjectHoursChart :project="project" :consumptions="detail.data.value?.consumos ?? []" />
      <section class="panel">
        <div class="section-heading">
          <h2>Consumos de horas</h2>
          <RouterLink class="btn btn-primary" :to="`/consumos/nuevo?proyecto_id=${id}`">+ Registrar consumo</RouterLink>
        </div>
        <ConsumptionTable :rows="detail.data.value?.consumos ?? []" :user="session.user" :return-to="`/proyectos/${id}`" />
      </section>
      <div class="summary-grid">
        <section v-for="[title, totals] in summaries" :key="title" class="panel">
          <h2>{{ title }}</h2>
          <div v-for="(hours, label) in totals" :key="label" class="summary-row">
            <span>{{ label }}</span><strong>{{ fmt(hours) }} h</strong>
          </div>
          <p v-if="!Object.keys(totals).length" class="muted">Sin horas registradas.</p>
        </section>
      </div>
    </template>
  </LoadState>
</template>
