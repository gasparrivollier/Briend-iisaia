import { afterEach, describe, expect, it, vi } from 'vitest'
import { api, APIError } from '@/api/client'

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

function mockFetch(...responses: (Response | Error)[]) {
  const fetch = vi.fn(async (_request: Request) => {
    const next = responses.shift()
    if (!next || next instanceof Error) throw next ?? new Error('sin respuesta')
    return next
  })
  vi.stubGlobal('fetch', fetch)
  return fetch
}

afterEach(() => vi.unstubAllGlobals())

describe('API client', () => {
  it('sends JSON with cookies and the latest rotated CSRF token on mutations only', async () => {
    const fetch = mockFetch(
      json({ user: null, csrf_token: 'first' }),
      json({ user: { recurso_id: 1 }, csrf_token: 'second' }),
      json([]),
      new Response(null, { status: 204 }),
    )
    await api.session()
    await api.login({ recurso_nombre: 'admin', password: 'x' })
    await api.roles()
    expect(await api.deleteRole(3)).toBeUndefined()

    const [session, login, roles, remove] = fetch.mock.calls.map(([request]) => request)
    expect(session!.headers.get('X-CSRF-Token')).toBeNull()
    expect(login!.headers.get('X-CSRF-Token')).toBe('first')
    expect(login!.headers.get('Content-Type')).toContain('application/json')
    expect(login!.credentials).toBe('same-origin')
    expect(roles!.headers.get('X-CSRF-Token')).toBeNull()
    expect(remove!.method).toBe('DELETE')
    expect(remove!.headers.get('X-CSRF-Token')).toBe('second')
    expect(await remove!.text()).toBe('{}')
  })

  it('maps the error contract to APIError without retrying', async () => {
    const fetch = mockFetch(json({ error: { code: 'csrf_invalid', message: 'La sesión venció.' } }, 400))
    const error = await api.saveRole({ rol_descripcion: 'X' }).catch((e) => e)
    expect(error).toBeInstanceOf(APIError)
    expect([error.status, error.code, error.message]).toEqual([400, 'csrf_invalid', 'La sesión venció.'])
    expect(fetch).toHaveBeenCalledTimes(1)
  })

  it('turns a non-JSON 413 (the proxy rejecting a big upload) into the friendly size message', async () => {
    mockFetch(new Response('Request Entity Too Large', { status: 413, headers: { 'Content-Type': 'text/plain' } }))
    const error = await api.roles().catch((e) => e)
    expect(error).toBeInstanceOf(APIError)
    expect([error.status, error.code, error.message]).toEqual([
      413,
      'http_413',
      'El archivo supera el tamaño máximo permitido (5 MiB).',
    ])
  })

  it('reports network failures and invalid responses in Spanish', async () => {
    mockFetch(new TypeError('Failed to fetch'))
    await expect(api.roles()).rejects.toMatchObject({ code: 'network_error', status: 0 })
    mockFetch(new Response('<html>', { status: 200, headers: { 'Content-Type': 'application/json' } }))
    await expect(api.roles()).rejects.toMatchObject({ code: 'invalid_response' })
  })

  it('uploads a file with the CSRF token to the entity endpoint and the confirm flag', async () => {
    const fetch = mockFetch(
      json({ user: null, csrf_token: 'tok' }),
      json({ entidad: 'roles', total: 1, validas: 1, errores_total: 0, errores: [], advertencias: [], creadas: 0, confirmada: false }),
    )
    // vitest's jsdom compat layer cannot turn a jsdom FormData into a Node Request body, so give the client
    // Node's own FormData (taken from a Node Response) for this test; the real multipart body is covered by e2e.
    const NodeFormData = (await new Response(new URLSearchParams({ a: 'b' })).formData()).constructor
    vi.stubGlobal('FormData', NodeFormData)
    await api.session()
    const result = await api.bulkUpload('roles', new File(['rol_descripcion\nQA\n'], 'roles.csv'), false)
    const request = fetch.mock.calls[1]![0]
    expect(result.validas).toBe(1)
    expect(request.method).toBe('POST')
    expect(new URL(request.url).pathname).toBe('/api/carga-masiva/roles')
    expect(new URL(request.url).searchParams.get('confirmar')).toBe('false')
    expect(request.headers.get('X-CSRF-Token')).toBe('tok')
  })
})
