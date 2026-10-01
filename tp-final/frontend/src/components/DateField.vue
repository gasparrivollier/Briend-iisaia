<script setup lang="ts">
// Wraps @vuepic/vue-datepicker to keep the native type="date" input's model contract
// (plain ISO 'YYYY-MM-DD' string) while fixing its month/year-navigation UX. `min`/`max`
// are ISO date strings; they're converted to local-midnight Dates (not `new Date(iso)`,
// which parses as UTC and can shift the bound by a day in UTC-3).
import { es } from 'date-fns/locale'
import { computed } from 'vue'
import { VueDatePicker } from '@vuepic/vue-datepicker'
import '@vuepic/vue-datepicker/dist/main.css'

defineOptions({ inheritAttrs: false })
const props = defineProps<{ name: string; label: string; min?: string; max?: string; required?: boolean }>()
const model = defineModel<string>({ default: '' })

function toLocalDate(iso?: string) {
  if (!iso) return undefined
  const [y, m, d] = iso.split('-').map((part) => Number(part))
  return new Date(y!, m! - 1, d!)
}
const minDate = computed(() => toLocalDate(props.min))
const maxDate = computed(() => toLocalDate(props.max))
</script>

<template>
  <div class="field">
    <label :for="name">{{ label }}</label>
    <VueDatePicker
      v-model="model"
      model-type="yyyy-MM-dd"
      :formats="{ input: 'dd/MM/yyyy' }"
      :locale="es"
      :time-config="{ enableTimePicker: false }"
      :min-date="minDate"
      :max-date="maxDate"
      :input-attrs="{ id: name, required: !!required, clearable: !required }"
      :text-input="{ format: 'dd/MM/yyyy' }"
      :aria-labels="{ input: label }"
      auto-apply
      v-bind="$attrs"
    />
  </div>
</template>

<style>
/* Approximate the app's .form-control look (src/styles/main.css) so the picker
   doesn't stand out from TextField/SelectField. Class names/variables per the
   installed @vuepic/vue-datepicker version (dp--… / --dp-…, not the older dp__…). */
.dp--input {
  border-color: #cdd9d7;
  padding: 11px 12px;
  border-radius: 8px;
  font-size: inherit;
  font-family: inherit;
}
.dp--theme-light {
  --dp-primary-color: var(--accent);
  --dp-border-radius: 8px;
  --dp-border-color-hover: var(--accent);
}
</style>
