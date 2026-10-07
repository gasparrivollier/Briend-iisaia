<script setup lang="ts">
import { computed } from 'vue'
import { indexViews, stateText, type Health } from '@/dashboard'
import { fmt } from '@/utils'

const props = defineProps<{ health: Health }>()
const bars = computed(() => [
  ['Tiempo transcurrido', props.health.porcentaje_tiempo],
  ['Horas consumidas', props.health.porcentaje_consumo],
  ['Avance real (manual)', props.health.porcentaje_avance],
] as [string, number][])
const indices = computed(() => indexViews(props.health))
const ICON = { bien: '✓', atencion: '!', critico: '✕' } as const
</script>

<template>
  <section class="panel dash-panel">
    <h2>Salud del proyecto</h2>
    <p class="muted">Tiempo, horas y avance, y qué tan alineados están entre sí. Horas ganadas: {{ fmt(health.horas_ganadas) }} h (avance × horas requeridas).</p>
    <div v-for="[name, value] in bars" :key="name" class="metric-bar">
      <div class="progress-label"><span>{{ name }}</span><strong>{{ fmt(value) }} %</strong></div>
      <div class="progress" role="progressbar" :aria-label="name" :aria-valuenow="Math.min(100, value)" aria-valuemin="0" aria-valuemax="100">
        <div class="progress-bar" :style="{ width: Math.max(0, Math.min(100, value)) + '%' }"></div>
      </div>
    </div>
    <div class="index-grid">
      <div v-for="item in indices" :key="item.title" class="index-card">
        <span class="muted">{{ item.title }}</span>
        <strong>{{ item.value }}</strong>
        <span class="index-state" :class="item.state ? `state-${item.state}` : ''">
          <span aria-hidden="true">{{ item.state ? ICON[item.state] : '–' }}</span> {{ stateText(item.state) }}
        </span>
        <p class="muted">{{ item.sentence }}</p>
      </div>
    </div>
  </section>
</template>
