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

const props = defineProps<{ id?: number }>()
const session = useSessionStore()
const catalogs = useQuery({ queryKey: ['catalogos'], queryFn: api.catalogs })
const existing = useQuery({
  queryKey: ['proyecto', () => props.id],
  queryFn: () => api.project(props.id!),
  enabled: () => !!props.id,
  refetchOnWindowFocus: false,
})

const form = reactive({
  proyecto_nombre: '', fecha_inicio: '', fecha_fin: '', horas_requeridas: '' as string | number,
  porcentaje_avance: '0' as string | number, owner_id: '', proyect_status: 'Pendiente',
})
watch(
  () => existing.data.value?.proyecto,
  (p) => {
    if (!p) return
    Object.assign(form, {
      proyecto_nombre: p.proyecto_nombre, fecha_inicio: p.fecha_inicio, fecha_fin: p.fecha_fin,
      horas_requeridas: p.horas_requeridas, porcentaje_avance: p.porcentaje_avance,
      owner_id: toText(p.owner_id), proyect_status: p.proyect_status,
    })
  },
  { immediate: true },
)

const dateReady = computed(() => !!form.fecha_inicio && !!form.fecha_fin)
const dateError = computed(() => (dateReady.value ? dateRangeError(form.fecha_inicio, form.fecha_fin) : null))

const denied = computed(() => {
  const user = session.user
  const owner = existing.data.value?.proyecto.owner_id
  if (!user || user.es_admin || (props.id && owner === undefined)) return null
  return owner === user.recurso_id ? null : new APIError('No podés editar este proyecto.', 403)
})

const { busy, submit } = useSubmit(async () => {
  const saved = await api.saveProject(
    {
      ...form,
      horas_requeridas: toNumber(form.horas_requeridas),
      porcentaje_avance: toNumber(form.porcentaje_avance),
      owner_id: session.user?.es_admin ? toNumber(form.owner_id) : undefined,
    },
    props.id,
  )
  return `/proyectos/${saved.proyecto_id}`
})
</script>

<template>
  <LoadState
    :loading="catalogs.isPending.value || (!!id && existing.isPending.value)"
    :error="denied ?? catalogs.error.value ?? existing.error.value"
    @retry="existing.refetch()"
  >
    <FormShell
      :title="id ? 'Editar proyecto' : 'Nuevo proyecto'" back="/proyectos" :busy="busy"
      :disabled="!dateReady || !!dateError" @submit="submit"
    >
      <TextField v-model="form.proyecto_nombre" name="proyecto_nombre" label="Nombre del proyecto" required />
      <div class="form-grid">
        <DateField v-model="form.fecha_inicio" name="fecha_inicio" label="Fecha de inicio" required />
        <DateField v-model="form.fecha_fin" name="fecha_fin" label="Fecha de fin prevista" required />
        <TextField v-model="form.horas_requeridas" name="horas_requeridas" label="Horas requeridas" type="number" required min="0" step="any" />
        <TextField v-model="form.porcentaje_avance" name="porcentaje_avance" label="Avance real (%)" type="number" required min="0" max="100" step="any" />
      </div>
      <p v-if="dateError" class="field-error">{{ dateError }}</p>
      <SelectField
        v-if="session.user?.es_admin" v-model="form.owner_id" name="owner_id" label="Responsable"
        :options="(catalogs.data.value?.recursos ?? []).map((r) => ({ value: r.recurso_id, label: r.recurso_nombre }))"
      />
      <SelectField
        v-model="form.proyect_status" name="proyect_status" label="Estado"
        :options="(catalogs.data.value?.estados ?? []).map((value) => ({ value, label: value }))"
      />
      <p class="muted">El avance real es manual e independiente del consumo de horas y del estado.</p>
    </FormShell>
  </LoadState>
</template>
