<script setup lang="ts">
import { api, type Consumption, type User } from '@/api/client'
import DeleteButton from '@/components/DeleteButton.vue'
import { fmt } from '@/utils'

defineProps<{ rows: Consumption[]; user: User; showProject?: boolean; returnTo?: string }>()
</script>

<template>
  <div class="table-responsive">
    <table class="table">
      <thead>
        <tr>
          <th v-if="showProject">Proyecto</th>
          <th>Tarea / recurso</th><th>Rol</th><th>Período</th><th class="text-end">Horas</th><th>Acciones</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="row.consumo_id">
          <td v-if="showProject"><RouterLink :to="`/proyectos/${row.proyecto_id}`">{{ row.proyecto_nombre }}</RouterLink></td>
          <td><strong>{{ row.tarea }}</strong><small class="d-block muted">{{ row.recurso_nombre }}</small></td>
          <td>{{ row.rol_descripcion }}</td>
          <td class="date-cell">{{ row.fecha_inicio }}<br />{{ row.fecha_fin }}</td>
          <td class="text-end">{{ fmt(row.horas_consumidas) }}</td>
          <td>
            <div v-if="user.es_admin || user.recurso_id === row.recurso_id" class="actions">
              <RouterLink class="btn btn-sm btn-outline-secondary" :to="`/consumos/${row.consumo_id}/editar`">Editar</RouterLink>
              <DeleteButton :remove="() => api.deleteConsumption(row.consumo_id)" :return-to="returnTo ?? '/proyectos'" />
            </div>
            <span v-else class="muted">Solo lectura</span>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="showProject ? 6 : 5" class="empty">Todavía no hay consumos registrados.</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>
