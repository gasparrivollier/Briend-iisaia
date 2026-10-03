<script setup lang="ts">
import { useQuery } from '@tanstack/vue-query'
import { computed, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '@/api/client'
import LoadState from '@/components/LoadState.vue'
import PageHeading from '@/components/PageHeading.vue'
import ProgressBar from '@/components/ProgressBar.vue'
import SelectField from '@/components/SelectField.vue'
import StatGrid from '@/components/StatGrid.vue'
import { useSessionStore } from '@/stores/session'
import { fmt, statusClass } from '@/utils'

const session = useSessionStore()
const alertsBusy = ref(false)
const alertsMessage = ref('')
const alertsFailed = ref(false)
async function runAlerts() {
  if (alertsBusy.value) return
  alertsBusy.value = true
  alertsMessage.value = ''
  alertsFailed.value = false
  try {
    const result = await api.runAlerts()
    alertsFailed.value = result.fallidos > 0
    alertsMessage.value = result.en_ejecucion
      ? 'Ya hay un control de alertas en ejecución. Intentá nuevamente cuando termine.'
      : `Control completado: ${result.vencidos} proyectos vencidos, ${result.enviados} correos enviados, ${result.sin_email} sin email y ${result.fallidos} envíos fallidos.`
  } catch (error) {
    alertsFailed.value = true
    alertsMessage.value = error instanceof Error ? error.message : 'No se pudo ejecutar el control.'
  } finally {
    alertsBusy.value = false
  }
}
const route = useRoute()
const router = useRouter()
const filters = computed(() => ({
  estado: String(route.query.estado ?? ''),
  responsable: String(route.query.responsable ?? ''),
}))
const form = reactive({ ...filters.value })
watch(filters, (value) => Object.assign(form, value))

const projects = useQuery({ queryKey: ['proyectos', filters], queryFn: () => api.projects(filters.value) })
const catalogs = useQuery({ queryKey: ['catalogos'], queryFn: api.catalogs })

const totals = computed(() => {
  const rows = projects.data.value ?? []
  const estimated = rows.reduce((sum, p) => sum + p.horas_requeridas, 0)
  const used = rows.reduce((sum, p) => sum + p.horas_consumidas, 0)
  return [
    ['Proyectos en vista', rows.length],
    ['Horas requeridas', fmt(estimated) + ' h'],
    ['Horas consumidas', fmt(used) + ' h'],
    ['Saldo de horas', fmt(estimated - used) + ' h'],
  ] as [string, string | number][]
})

function applyFilters() {
  const query = Object.fromEntries(Object.entries(form).filter(([, value]) => value))
  void router.push({ name: 'projects', query })
}
function retry() {
  void projects.refetch()
  void catalogs.refetch()
}
</script>

<template>
  <PageHeading title="Proyectos" subtitle="El avance de tu equipo, en perspectiva." eyebrow="VISTA GENERAL">
    <RouterLink v-if="session.user?.es_admin" class="btn btn-primary" to="/proyectos/nuevo">+ Nuevo proyecto</RouterLink>
  </PageHeading>
  <div v-if="session.user?.es_admin" class="panel mb-3">
    <button type="button" class="btn btn-outline-primary" :disabled="alertsBusy" @click="runAlerts">
      {{ alertsBusy ? 'Ejecutando control…' : 'Ejecutar control de alertas' }}
    </button>
    <p class="muted mt-2 mb-0">Revisa fechas vencidas de todos los proyectos y envía avisos al owner. Puede reenviar avisos de hoy.</p>
    <p v-if="alertsMessage" role="status" class="mt-2 mb-0" :class="alertsFailed ? 'text-danger' : ''">{{ alertsMessage }}</p>
  </div>
  <LoadState
    :loading="projects.isPending.value || catalogs.isPending.value"
    :error="projects.error.value ?? catalogs.error.value"
    @retry="retry"
  >
    <StatGrid :items="totals" />
    <form class="filters panel" @submit.prevent="applyFilters">
      <SelectField
        v-model="form.estado" name="estado" label="Estado" blank="Todos los estados" :required="false"
        :options="(catalogs.data.value?.estados ?? []).map((value) => ({ value, label: value }))"
      />
      <SelectField
        v-model="form.responsable" name="responsable" label="Responsable" blank="Todos los responsables" :required="false"
        :options="(catalogs.data.value?.recursos ?? []).map((r) => ({ value: r.recurso_id, label: r.recurso_nombre }))"
      />
      <button class="btn btn-primary">Filtrar</button>
      <RouterLink class="btn btn-outline-secondary" to="/proyectos">Limpiar</RouterLink>
    </form>
    <div class="project-grid">
      <article v-for="p in projects.data.value" :key="p.proyecto_id" class="panel project-card">
        <div class="card-top">
          <span :class="statusClass(p.proyect_status)">{{ p.proyect_status }}</span>
          <span class="muted">#{{ p.proyecto_id }}</span>
        </div>
        <h2><RouterLink :to="`/proyectos/${p.proyecto_id}`">{{ p.proyecto_nombre }}</RouterLink></h2>
        <p class="muted">Responsable · {{ p.responsable }}</p>
        <ProgressBar :value="p.porcentaje_avance" />
        <div class="hours">
          <span><strong>{{ fmt(p.horas_consumidas) }}</strong> / {{ fmt(p.horas_requeridas) }} h consumidas</span>
          <span>{{ fmt(p.porcentaje_consumo) }} %</span>
        </div>
        <p :class="p.exceso > 0 ? 'overrun' : 'muted'">Saldo: {{ fmt(p.saldo) }} h · Exceso: {{ fmt(p.exceso) }} h</p>
        <div class="card-bottom">
          <small>{{ p.fecha_inicio }} → {{ p.fecha_fin }}</small>
          <RouterLink :to="`/proyectos/${p.proyecto_id}`">Ver proyecto →</RouterLink>
        </div>
      </article>
      <div v-if="!projects.data.value?.length" class="panel empty">
        <h2>No hay proyectos para mostrar</h2>
        <p>Creá un proyecto o ajustá los filtros para comenzar.</p>
      </div>
    </div>
  </LoadState>
</template>
