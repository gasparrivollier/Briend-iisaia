<script setup lang="ts">
import { keepPreviousData, useQuery } from '@tanstack/vue-query'
import { computed, ref } from 'vue'
import { api } from '@/api/client'
import DistributionCharts from '@/components/dashboard/DistributionCharts.vue'
import ExecutionPanel from '@/components/dashboard/ExecutionPanel.vue'
import HealthPanel from '@/components/dashboard/HealthPanel.vue'
import PacePanel from '@/components/dashboard/PacePanel.vue'
import PeriodHoursChart from '@/components/dashboard/PeriodHoursChart.vue'
import TaskHealthPanel from '@/components/dashboard/TaskHealthPanel.vue'
import LoadState from '@/components/LoadState.vue'
import PageHeading from '@/components/PageHeading.vue'
import { isoToLocal } from '@/dashboard'

const props = defineProps<{ id: number }>()
const period = ref<'semana' | 'mes'>('semana')
const report = useQuery({
  queryKey: computed(() => ['reporte', props.id, period.value]),
  queryFn: () => api.projectReport(props.id, period.value),
  placeholderData: keepPreviousData,
})
// Same key as the detail page, so arriving from it reuses the cached project and its consumptions.
const detail = useQuery({ queryKey: ['proyecto', () => props.id], queryFn: () => api.project(props.id) })
const project = computed(() => report.data.value?.proyecto)
</script>

<template>
  <LoadState :loading="report.isPending.value || detail.isPending.value" :error="report.error.value ?? detail.error.value" @retry="report.refetch(); detail.refetch()">
    <template v-if="report.data.value && project">
      <RouterLink :to="`/proyectos/${id}`">← {{ project.proyecto_nombre }}</RouterLink>
      <PageHeading
        title="Dashboard del proyecto"
        :subtitle="`${project.proyecto_nombre} · ${project.responsable} · ${project.proyect_status} · datos al ${isoToLocal(report.data.value.fecha_corte)}`"
        eyebrow="REPORTING"
      />
      <HealthPanel :health="report.data.value.salud" />
      <PeriodHoursChart :periods="report.data.value.periodos" :period="period" @update:period="period = $event" />
      <PacePanel :report="report.data.value" :consumptions="detail.data.value?.consumos ?? []" />
      <ExecutionPanel :report="report.data.value" />
      <TaskHealthPanel :report="report.data.value" />
      <DistributionCharts :report="report.data.value" />
    </template>
  </LoadState>
</template>
