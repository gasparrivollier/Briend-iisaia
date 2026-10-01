<script setup lang="ts">
import { useQuery } from '@tanstack/vue-query'
import { computed, reactive, watch } from 'vue'
import { api, APIError } from '@/api/client'
import DateField from '@/components/DateField.vue'
import FormShell from '@/components/FormShell.vue'
import LoadState from '@/components/LoadState.vue'
import SelectField from '@/components/SelectField.vue'
import TextField from '@/components/TextField.vue'
import { useSubmit } from '@/composables/submit'
import { useSessionStore } from '@/stores/session'
import { dateRangeError, toNumber, toText } from '@/utils'

// New task: /proyectos/:id/tareas/nueva (projectId). Edit: /tareas/:id/editar (id).
const props = defineProps<{ id?: number; projectId?: number }>()
const session = useSessionStore()
const catalogs = useQuery({ queryKey: ['catalogos'], queryFn: api.catalogs })
const existing = useQuery({
  queryKey: ['tarea', () => props.id],
  queryFn: () => api.task(props.id!),
  enabled: () => !!props.id,
  refetchOnWindowFocus: false,
})
const projectId = computed(() => props.projectId ?? existing.data.value?.proyecto_id)
const project = useQuery({
  queryKey: ['proyecto', projectId],
  queryFn: () => api.project(projectId.value!),
  enabled: () => !!projectId.value,
})
const p = computed(() => project.data.value?.proyecto)

const form = reactive({
  tarea_nombre: '', fecha_inicio: '', fecha_fin: '', porcentaje_avance: '0' as string | number, recurso_id: '',
})
watch(
  () => existing.data.value,
  (t) => {
    if (!t) return
    Object.assign(form, {
      tarea_nombre: t.tarea_nombre, fecha_inicio: t.fecha_inicio, fecha_fin: t.fecha_fin,
      porcentaje_avance: t.porcentaje_avance, recurso_id: toText(t.recurso_id),
    })
  },
  { immediate: true },
)

const denied = computed(() => {
  const user = session.user
  if (!user || user.es_admin || !p.value) return null
  return p.value.owner_id === user.recurso_id
    ? null
    : new APIError('Solo el responsable o un administrador puede editar las tareas de este proyecto.', 403)
})
const back = computed(() => `/proyectos/${projectId.value ?? ''}`)

const dateReady = computed(() => !!form.fecha_inicio && !!form.fecha_fin)
// Mirrors backend/pulso/routers/tasks.py (OUTSIDE_PROJECT) and schemas.py (DateRange.ordered),
// so the live message matches what the API would otherwise reject at submit time.
const dateError = computed(() => {
  if (!dateReady.value || !p.value) return null
  if (form.fecha_inicio < p.value.fecha_inicio || form.fecha_fin > p.value.fecha_fin) {
    return `Las fechas de la tarea deben estar dentro de las del proyecto (${p.value.fecha_inicio} → ${p.value.fecha_fin}).`
  }
  return dateRangeError(form.fecha_inicio, form.fecha_fin)
})

const { busy, submit } = useSubmit(async () => {
  const body = {
    ...form,
    porcentaje_avance: toNumber(form.porcentaje_avance),
    recurso_id: form.recurso_id ? toNumber(form.recurso_id) : null,
  }
  if (props.id) await api.updateTask(props.id, body)
  else await api.createTask(projectId.value!, body)
  return back.value
})
</script>

<template>
  <LoadState
    :loading="catalogs.isPending.value || (!!id && existing.isPending.value) || (!!projectId && project.isPending.value)"
    :error="denied ?? catalogs.error.value ?? existing.error.value ?? project.error.value"
    @retry="existing.refetch()"
  >
    <FormShell
      :title="id ? 'Editar tarea' : 'Nueva tarea'" :back="back" :busy="busy"
      :disabled="!dateReady || !!dateError" @submit="submit"
    >
      <p v-if="p" class="muted">Proyecto {{ p.proyecto_nombre }} · {{ p.fecha_inicio }} → {{ p.fecha_fin }}</p>
      <TextField v-model="form.tarea_nombre" name="tarea_nombre" label="Nombre de la tarea" required />
      <div class="form-grid">
        <DateField v-model="form.fecha_inicio" name="fecha_inicio" label="Fecha de inicio" required :min="p?.fecha_inicio" :max="p?.fecha_fin" />
        <DateField
          v-model="form.fecha_fin" name="fecha_fin" label="Fecha de fin" required
          :min="form.fecha_inicio || p?.fecha_inicio" :max="p?.fecha_fin"
        />
        <TextField v-model="form.porcentaje_avance" name="porcentaje_avance" label="Avance (%)" type="number" required min="0" max="100" step="any" />
        <SelectField
          v-model="form.recurso_id" name="recurso_id" label="Responsable de la tarea" blank="Sin asignar" :required="false"
          :options="(catalogs.data.value?.recursos ?? []).map((r) => ({ value: r.recurso_id, label: r.recurso_nombre }))"
        />
      </div>
      <p class="muted">Las fechas deben estar dentro de las del proyecto.</p>
      <p v-if="dateError" class="field-error">{{ dateError }}</p>
    </FormShell>
  </LoadState>
</template>
