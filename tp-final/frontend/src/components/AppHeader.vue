<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { handleError } from '@/composables/notice'
import { useSessionStore } from '@/stores/session'

const session = useSessionStore()
const router = useRouter()
const busy = ref(false)

async function logout() {
  busy.value = true
  try {
    await session.logout()
    await router.push({ name: 'login' })
  } catch (error) {
    await handleError(error, router)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <header class="topbar">
    <RouterLink class="brand" to="/proyectos"><span class="brand-icon">P</span> Pulso</RouterLink>
    <template v-if="session.user">
      <nav aria-label="Navegación principal">
        <RouterLink to="/proyectos">Proyectos</RouterLink>
        <RouterLink to="/carga-masiva">Carga masiva</RouterLink>
        <template v-if="session.user.es_admin">
          <RouterLink to="/recursos">Recursos</RouterLink>
          <RouterLink to="/roles">Roles</RouterLink>
        </template>
      </nav>
      <div class="account">
        <RouterLink to="/password">{{ session.user.recurso_nombre }}</RouterLink>
        <button class="btn btn-sm btn-outline-secondary" :disabled="busy" @click="logout">Salir</button>
      </div>
    </template>
  </header>
</template>
