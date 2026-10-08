<script setup lang="ts">
import type { Schemas } from '@/api/client'

defineProps<{ result: Schemas['CargaResultado']; busy: boolean }>()
defineEmits<{ confirm: [] }>()
</script>

<template>
  <section class="panel">
    <h2>Vista previa</h2>
    <p aria-live="polite">
      <strong>{{ result.total }}</strong> filas leídas · <strong>{{ result.validas }}</strong> válidas ·
      <strong>{{ result.errores_total }}</strong> errores
    </p>

    <div v-if="result.errores_total" class="table-responsive">
      <p class="status status-pausado">Corregí el archivo y volvé a subirlo: no se guardó nada.</p>
      <table class="table">
        <caption>Errores por fila</caption>
        <thead><tr><th>Fila</th><th>Campo</th><th>Error</th></tr></thead>
        <tbody>
          <tr v-for="(issue, index) in result.errores" :key="index">
            <td>{{ issue.fila }}</td><td>{{ issue.campo ?? '—' }}</td><td>{{ issue.mensaje }}</td>
          </tr>
        </tbody>
      </table>
      <p v-if="result.errores_total > result.errores.length" class="muted">
        Se muestran los primeros {{ result.errores.length }} errores.
      </p>
    </div>

    <div v-if="result.advertencias.length" class="table-responsive">
      <table class="table">
        <caption>Advertencias (no impiden la carga)</caption>
        <thead><tr><th>Fila</th><th>Campo</th><th>Aviso</th></tr></thead>
        <tbody>
          <tr v-for="(issue, index) in result.advertencias" :key="index">
            <td>{{ issue.fila }}</td><td>{{ issue.campo ?? '—' }}</td><td>{{ issue.mensaje }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="actions">
      <button v-if="!result.errores_total && result.validas" class="btn btn-primary" :disabled="busy" @click="$emit('confirm')">
        Confirmar carga de {{ result.validas }} filas
      </button>
    </div>
  </section>
</template>
