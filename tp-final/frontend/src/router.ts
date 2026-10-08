import { createRouter, createWebHistory, type RouteLocationNormalized } from 'vue-router'
import type { User } from '@/api/client'
import { notice } from '@/composables/notice'
import { useSessionStore } from '@/stores/session'

declare module 'vue-router' {
  interface RouteMeta {
    title?: string
    admin?: boolean
  }
}

const withId = (route: RouteLocationNormalized) => ({ id: Number(route.params.id) })

export const routes = [
  { path: '/', redirect: '/proyectos' },
  { path: '/login', name: 'login', component: () => import('@/views/LoginView.vue'), meta: { title: 'Ingresar' } },
  { path: '/password', name: 'password', component: () => import('@/views/PasswordView.vue'), meta: { title: 'Cambiar contraseña' } },
  { path: '/proyectos', name: 'projects', component: () => import('@/views/ProjectsView.vue'), meta: { title: 'Proyectos' } },
  { path: '/proyectos/nuevo', name: 'project-new', component: () => import('@/views/ProjectFormView.vue'), meta: { title: 'Nuevo proyecto', admin: true } },
  { path: '/proyectos/:id(\\d+)', name: 'project', component: () => import('@/views/ProjectDetailView.vue'), props: withId, meta: { title: 'Proyecto' } },
  { path: '/proyectos/:id(\\d+)/dashboard', name: 'project-dashboard', component: () => import('@/views/ProjectDashboardView.vue'), props: withId, meta: { title: 'Dashboard del proyecto' } },
  { path: '/proyectos/:id(\\d+)/editar', name: 'project-edit', component: () => import('@/views/ProjectFormView.vue'), props: withId, meta: { title: 'Editar proyecto' } },
  { path: '/proyectos/:id(\\d+)/tareas/nueva', name: 'task-new', component: () => import('@/views/TaskFormView.vue'), props: (route: RouteLocationNormalized) => ({ projectId: Number(route.params.id) }), meta: { title: 'Nueva tarea' } },
  { path: '/tareas/:id(\\d+)/editar', name: 'task-edit', component: () => import('@/views/TaskFormView.vue'), props: withId, meta: { title: 'Editar tarea' } },
  { path: '/consumos/nuevo', name: 'consumption-new', component: () => import('@/views/ConsumptionFormView.vue'), meta: { title: 'Registrar consumo' } },
  { path: '/consumos/:id(\\d+)/editar', name: 'consumption-edit', component: () => import('@/views/ConsumptionFormView.vue'), props: withId, meta: { title: 'Editar consumo' } },
  { path: '/recursos', name: 'resources', component: () => import('@/views/ResourcesView.vue'), meta: { title: 'Recursos', admin: true } },
  { path: '/recursos/nuevo', name: 'resource-new', component: () => import('@/views/ResourceFormView.vue'), meta: { title: 'Nuevo recurso', admin: true } },
  { path: '/recursos/:id(\\d+)/editar', name: 'resource-edit', component: () => import('@/views/ResourceFormView.vue'), props: withId, meta: { title: 'Editar recurso', admin: true } },
  { path: '/roles', name: 'roles', component: () => import('@/views/RolesView.vue'), meta: { title: 'Roles', admin: true } },
  { path: '/roles/nuevo', name: 'role-new', component: () => import('@/views/RoleFormView.vue'), meta: { title: 'Nuevo rol', admin: true } },
  { path: '/roles/:id(\\d+)/editar', name: 'role-edit', component: () => import('@/views/RoleFormView.vue'), props: withId, meta: { title: 'Editar rol', admin: true } },
  { path: '/carga-masiva', name: 'bulk-upload', component: () => import('@/views/BulkUploadView.vue'), meta: { title: 'Carga masiva' } },
  { path: '/:pathMatch(.*)*', name: 'not-found', component: () => import('@/views/NotFoundView.vue'), meta: { title: 'Página no encontrada' } },
]

/** Navigation rules shared with the previous frontend. Returns a route name to redirect to, if any. */
export function redirectFor(user: User | null, target: RouteLocationNormalized): string | null {
  if (!user) return target.name === 'login' ? null : 'login'
  if (user.debe_cambiar_password) return target.name === 'password' ? null : 'password'
  if (target.name === 'login') return 'projects'
  if (target.meta.admin && !user.es_admin) return 'projects'
  return null
}

export function createAppRouter() {
  const router = createRouter({ history: createWebHistory(), routes })

  router.beforeEach(async (to) => {
    const session = useSessionStore()
    try {
      await session.refresh() // every navigation re-reads the session, like the previous frontend
    } catch {
      // Network problems surface on the page itself; keep the last known user.
    }
    const name = redirectFor(session.user, to)
    return name && name !== to.name ? { name, replace: true } : true
  })

  router.afterEach((to) => {
    notice.text = ''
    document.title = `${to.meta.title ?? 'Proyectos'} · Pulso`
    window.scrollTo?.(0, 0)
  })

  return router
}
