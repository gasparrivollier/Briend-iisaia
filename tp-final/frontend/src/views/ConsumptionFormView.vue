<script setup lang="ts">
import { useQuery } from '@tanstack/vue-query'
import { computed, reactive, watch } from 'vue'
import { useRoute } from 'vue-router'
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
const route = useRoute()
const catalogs = useQuery({ queryKey: ['catalogos'], queryFn: api.catalogs })
const projects = useQuery({ queryKey: ['proyectos', {}], queryFn: () => api.projects({}) })
const existing = useQuery({
  queryKey: ['consumo', () => props.id],
  queryFn: () => api.consumption(props.id!),
  enabled: () => !!props.id,
  refetchOnWindowFocus: false,
})

const form = reactive({
  proyecto_id: toText(route.query.proyecto_id as string | undefined),
  recurso_id: toText(session.user?.recurso_id),
  rol_id: '', tarea: '', fecha_inicio: '', fecha_fin: '', horas_consumidas: '' as string | number,
})
watch(
  () => existing.data.value,
  (c) => {
    if (!c) return
    Object.assign(form, {
      proyecto_id: toText(c.proyecto_id), recurso_id: toText(c.recurso_id), rol_id: toText(c.rol_id),
      tarea: c.tarea, fecha_inicio: c.fecha_inicio, fecha_fin: c.fecha_fin, horas_consumidas: c.horas_consumidas,
    })
  },
  { immediate: true },
)

const denied = computed(() => {
  const user = session.user
  const owner = existing.data.value?.recurso_id
  if (!user || user.es_admin || owner === undefined || owner === user.recurso_id) return null
  return new APIError('Solo podés modificar tus propios consumos.', 403)
})
const unavailable = computed(
  () => !projects.data.value?.length || !catalogs.data.value?.roles.length,
)
const dateReady = computed(() => !!form.fecha_inicio && !!form.fecha_fin)
const dateError = computed(() => (dateReady.value ? dateRangeError(form.fecha_inicio, form.fecha_fin) : null))

const { busy, submit } = useSubmit(async () => {
  const saved = await api.saveConsumption(
    {
      ...form,
      proyecto_id: toNumber(form.proyecto_id),
      rol_id: toNumber(form.rol_id),
      recurso_id: session.user?.es_admin ? toNumber(form.recurso_id) : undefined,
      horas_consumidas: toNumber(form.horas_consumidas),
    },
    props.id,
  )
  return `/proyectos/${saved.proyecto_id}`
})

const back = computed(() => {
  const proyectoId = existing.data.value?.proyecto_id ?? toNumber(form.proyecto_id)
  return proyectoId ? `/proyectos/${proyectoId}` : '/proyectos'
})
</script>

<template>
  <LoadState
    :loading="catalogs.isPending.value || projects.isPending.value || (!!id && existing.isPending.value)"
    :error="denied ?? catalogs.error.value ?? projects.error.value ?? existing.error.value"
    @retry="existing.refetch()"
  >
    <FormShell
      :title="id ? 'Editar consumo' : 'Registrar consumo'" :back="back"
      :disabled="unavailable || !dateReady || !!dateError" :busy="busy" @submit="submit"
    >
      <div v-if="unavailable" class="alert alert-warning">
        Se necesita al menos un proyecto y un rol para registrar horas. Contactá al administrador.
      </div>
      <SelectField
        v-model="form.proyecto_id" name="proyecto_id" label="Proyecto"
        :options="(projects.data.value ?? []).map((p) => ({ value: p.proyecto_id, label: p.proyecto_nombre }))"
      />
      <SelectField
        v-if="session.user?.es_admin" v-model="form.recurso_id" name="recurso_id" label="Recurso"
        :options="(catalogs.data.value?.recursos ?? []).map((r) => ({ value: r.recurso_id, label: r.recurso_nombre }))"
      />
      <p v-else>Recurso: <strong>{{ session.user?.recurso_nombre }}</strong></p>
      <SelectField
        v-model="form.rol_id" name="rol_id" label="Rol desempeñado"
        :options="(catalogs.data.value?.roles ?? []).map((r) => ({ value: r.rol_id, label: r.rol_descripcion }))"
      />
      <TextField v-model="form.tarea" name="tarea" label="Tarea realizada" required />
      <div class="form-grid">
        <DateField v-model="form.fecha_inicio" name="fecha_inicio" label="Fecha de inicio" required />
        <DateField v-model="form.fecha_fin" name="fecha_fin" label="Fecha de fin" required />
      </div>
      <p v-if="dateError" class="field-error">{{ dateError }}</p>
      <TextField v-model="form.horas_consumidas" name="horas_consumidas" label="Horas consumidas" type="number" required min="0" step="any" />
    </FormShell>
  </LoadState>
</template>
