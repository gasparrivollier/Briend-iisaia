<script setup lang="ts">
import { computed, ref } from 'vue'
import { stackedHours, type Period } from '@/dashboard'
import BarChart from './BarChart.vue'

const props = defineProps<{ periods: Period[]; period: 'semana' | 'mes' }>()
const emit = defineEmits<{ 'update:period': [value: 'semana' | 'mes'] }>()
const by = ref<'por_rol' | 'por_recurso'>('por_rol')
const data = computed(() => stackedHours(props.periods, props.period, by.value))
const label = computed(() => `Horas por ${props.period} y por ${by.value === 'por_rol' ? 'rol' : 'recurso'}`)
</script>

<template>
  <section class="panel dash-panel">
    <div class="section-heading">
      <h2>Horas por período</h2>
      <div class="actions">
        <select class="form-select" aria-label="Agrupar por período" :value="period" @change="emit('update:period', ($event.target as HTMLSelectElement).value as 'semana' | 'mes')">
          <option value="semana">Por semana</option>
          <option value="mes">Por mes</option>
        </select>
        <select v-model="by" class="form-select" aria-label="Apilar por">
          <option value="por_rol">Por rol</option>
          <option value="por_recurso">Por recurso</option>
        </select>
      </div>
    </div>
    <p class="muted">Las horas de cada consumo se reparten uniformemente entre sus fechas, igual que en el gráfico de horas acumuladas.</p>
    <BarChart v-if="periods.length" :data="data" :label="label" stacked />
    <p v-else class="muted">Sin consumos registrados.</p>
  </section>
</template>
