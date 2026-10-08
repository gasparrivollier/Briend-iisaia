<script setup lang="ts">
import { useQuery, useQueryClient } from '@tanstack/vue-query'
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { api, type Schemas } from '@/api/client'
import { ACCEPT, availableEntities, MAX_UPLOAD_MESSAGE, tooLarge } from '@/bulk'
import BulkResult from '@/components/BulkResult.vue'
import LoadState from '@/components/LoadState.vue'
import PageHeading from '@/components/PageHeading.vue'
import SelectField from '@/components/SelectField.vue'
import { handleError, notice, showNotice } from '@/composables/notice'
import { useSessionStore } from '@/stores/session'

const session = useSessionStore()
const router = useRouter()
const queryClient = useQueryClient()
const projects = useQuery({ queryKey: ['projects', 'bulk'], queryFn: () => api.projects({}), refetchOnWindowFocus: false })

const entities = computed(() => (session.user ? availableEntities(session.user, projects.data.value ?? []) : []))
const options = computed(() => entities.value.map((e) => ({ value: e.key, label: e.label })))
const entity = ref('')
const selected = computed(() => entities.value.find((e) => e.key === entity.value))
const file = ref<File | null>(null)
const result = ref<Schemas['CargaResultado'] | null>(null)
const busy = ref(false)
const input = ref<HTMLInputElement | null>(null)

watch(entity, () => (result.value = null))

function pick(event: Event) {
  const target = event.target as HTMLInputElement
  const picked = target.files?.[0] ?? null
  result.value = null
  if (picked && tooLarge(picked)) {
    showNotice(MAX_UPLOAD_MESSAGE)
    target.value = ''
    file.value = null
    return
  }
  file.value = picked
}

async function send(confirm: boolean) {
  if (!entity.value || !file.value) return
  busy.value = true
  notice.text = ''
  try {
    const response = await api.bulkUpload(entity.value, file.value, confirm)
    if (response.confirmada) {
      await queryClient.invalidateQueries()
      showNotice(`Se cargaron ${response.creadas} registros de ${selected.value?.label.toLowerCase()}.`, 'success')
      result.value = null
      file.value = null
      if (input.value) input.value.value = ''
    } else {
      result.value = response
    }
  } catch (error) {
    await handleError(error, router)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <PageHeading title="Carga masiva" subtitle="Subí un archivo .csv, .xlsx o .txt; vas a ver una vista previa antes de guardar." />
  <LoadState :loading="projects.isPending.value" :error="projects.error.value" @retry="projects.refetch()">
    <form class="panel editor" @submit.prevent="send(false)">
      <SelectField v-model="entity" name="entidad" label="¿Qué querés cargar?" :options="options" :disabled="busy" />
      <p v-if="selected" class="muted">
        Columnas: {{ selected.columns }}.
        <a :href="api.bulkTemplateUrl(selected.key)" download>Descargar plantilla</a>
      </p>
      <div class="field">
        <label for="archivo">Archivo (.csv, .xlsx o .txt, hasta 5 MiB)</label>
        <input id="archivo" ref="input" type="file" class="form-control" :accept="ACCEPT" required @click="($event.target as HTMLInputElement).value = ''" @change="pick" />
      </div>
      <div class="actions">
        <button class="btn btn-primary" :disabled="busy || !entity || !file">Vista previa</button>
      </div>
    </form>
    <BulkResult v-if="result" :result="result" :busy="busy" @confirm="send(true)" />
  </LoadState>
</template>
