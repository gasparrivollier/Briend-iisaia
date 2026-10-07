<script setup lang="ts">
import { BarElement, CategoryScale, Chart as ChartJS, Legend, LinearScale, Tooltip, type ChartData, type ChartOptions } from 'chart.js'
import { computed } from 'vue'
import { Bar } from 'vue-chartjs'
import { fmt } from '@/utils'

ChartJS.register(BarElement, CategoryScale, LinearScale, Tooltip, Legend)

const props = defineProps<{
  data: ChartData<'bar'>
  label: string
  horizontal?: boolean
  stacked?: boolean
  notes?: string[] // extra tooltip line per category
}>()

const INK = '#65767a'
const GRID = '#e2e8f0'
const multi = computed(() => props.data.datasets.length > 1)
const rows = computed(() => (props.data.labels ?? []).length)
const height = computed(() => (props.horizontal ? Math.max(140, rows.value * 36 + 50) : 280))
const options = computed<ChartOptions<'bar'>>(() => ({
  responsive: true,
  maintainAspectRatio: false,
  indexAxis: props.horizontal ? 'y' : 'x',
  datasets: { bar: { maxBarThickness: 28, borderRadius: props.stacked ? 0 : 4 } },
  scales: {
    x: { stacked: props.stacked, grid: { display: !!props.horizontal, color: GRID }, ticks: { color: INK }, border: { display: false } },
    y: { stacked: props.stacked, beginAtZero: true, grid: { display: !props.horizontal, color: GRID }, ticks: { color: INK }, border: { display: false } },
  },
  plugins: {
    legend: { display: multi.value, position: 'bottom', labels: { color: INK, usePointStyle: true, boxWidth: 8 } },
    tooltip: {
      callbacks: {
        label: (item) => `${item.dataset.label}: ${fmt(item.parsed[props.horizontal ? 'x' : 'y'])} h`,
        afterLabel: (item) => props.notes?.[item.dataIndex] ?? '',
      },
    },
  },
}))
</script>

<template>
  <div class="chart-box" :style="{ height: height + 'px' }">
    <Bar :data="data" :options="options" role="img" :aria-label="label" />
  </div>
  <details class="chart-table">
    <summary>Ver como tabla</summary>
    <div class="table-responsive">
      <table class="table">
        <thead>
          <tr><th>{{ label }}</th><th v-for="dataset in data.datasets" :key="dataset.label">{{ dataset.label }} (h)</th></tr>
        </thead>
        <tbody>
          <tr v-for="(name, index) in data.labels" :key="String(name)">
            <td>{{ name }}</td>
            <td v-for="dataset in data.datasets" :key="dataset.label">{{ fmt(dataset.data[index] as number) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </details>
</template>
