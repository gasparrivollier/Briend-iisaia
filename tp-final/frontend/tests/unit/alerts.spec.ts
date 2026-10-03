import { mount, flushPromises } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import { QueryClient, VueQueryPlugin } from '@tanstack/vue-query'
import { createMemoryHistory, createRouter } from 'vue-router'
import ProjectsView from '@/views/ProjectsView.vue'

const mocks = vi.hoisted(() => ({ session: { user: { es_admin: true } }, run: vi.fn() }))
vi.mock('@/stores/session', () => ({ useSessionStore: () => mocks.session }))
vi.mock('@/api/client', () => ({ api: {
  runAlerts: mocks.run, projects: async () => [],
  catalogs: async () => ({ estados: [], recursos: [], roles: [] }),
} }))
function render() {
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/:p(.*)*', component: {} }] })
  return mount(ProjectsView, {
    global: { plugins: [router, [VueQueryPlugin, { queryClient: new QueryClient() }]] },
  })
}
describe('manual alerts', () => {
  it('hides the action from non-admin users', () => {
    mocks.session.user.es_admin = false
    const wrapper = render()
    expect(wrapper.text()).not.toContain('Ejecutar control de alertas')
    wrapper.unmount()
  })
  it('disables while running, reports results and recovers from failures', async () => {
    mocks.session.user.es_admin = true
    let finish!: (value: unknown) => void
    mocks.run.mockImplementationOnce(() => new Promise(resolve => { finish = resolve }))
    const wrapper = render()
    const button = wrapper.get('button.btn-outline-primary')
    await button.trigger('click')
    expect(button.attributes('disabled')).toBeDefined()
    finish({ vencidos: 3, enviados: 1, sin_email: 1, fallidos: 1, en_ejecucion: false })
    await flushPromises()
    expect(wrapper.get('[role="status"]').text()).toContain('3 proyectos vencidos, 1 correos enviados')
    expect(button.attributes('disabled')).toBeUndefined()
    mocks.run.mockRejectedValueOnce(new Error('No se pudo conectar'))
    await button.trigger('click')
    await flushPromises()
    expect(wrapper.get('[role="status"]').text()).toContain('No se pudo conectar')
    expect(button.attributes('disabled')).toBeUndefined()
    wrapper.unmount()
  })
})
