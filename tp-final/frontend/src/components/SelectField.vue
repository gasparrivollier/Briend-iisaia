<script setup lang="ts">
withDefaults(
  defineProps<{
    name: string
    label: string
    options: { value: string | number; label: string }[]
    blank?: string
    required?: boolean
    disabled?: boolean
  }>(),
  { blank: 'Seleccionar…', required: true },
)
const model = defineModel<string | number | null>()
</script>

<template>
  <div class="field">
    <label :for="name">{{ label }}</label>
    <select :id="name" v-model="model" class="form-select" :name="name" :required="required" :disabled="disabled">
      <option value="">{{ blank }}</option>
      <option v-for="option in options" :key="option.value" :value="String(option.value)">{{ option.label }}</option>
    </select>
  </div>
</template>
