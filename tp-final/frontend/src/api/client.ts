// Typed HTTP client generated from the FastAPI OpenAPI schema (`npm run gen:api`).
// The frontend only knows the HTTP contract; it never talks to the database.
import createClient from 'openapi-fetch'
import type { components, paths } from './schema'

export type Schemas = components['schemas']
export type User = Schemas['UsuarioOut']
export type Project = Schemas['ProyectoResumen']
export type Consumption = Schemas['ConsumoListado']
export type Task = Schemas['TareaOut']

export class APIError extends Error {
  constructor(
    message: string,
    public status: number,
    public code?: string,
  ) {
    super(message)
  }
}

type ErrorBody = { error?: { code?: string; message?: string } }
type Result<T> = { data?: T; error?: unknown; response: Response }

let csrfToken = ''

// Always same origin (Vite dev proxy / Caddy forward /api); absolute so it also works outside a browser.
const origin = typeof window === 'undefined' ? '' : window.location.origin
export const http = createClient<paths>({
  baseUrl: origin,
  credentials: 'same-origin',
  fetch: (request) => globalThis.fetch(request), // resolved per call (lets tests stub fetch)
})

http.use({
  onRequest({ request }) {
    request.headers.set('Accept', 'application/json')
    if (request.method !== 'GET') request.headers.set('X-CSRF-Token', csrfToken)
    return request
  },
})

/** Resolve an openapi-fetch call: throws APIError on failure, remembers rotated CSRF tokens. */
export async function call<T>(pending: Promise<Result<T>>): Promise<T> {
  let result: Result<T>
  try {
    result = await pending
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    if (error instanceof SyntaxError) {
      throw new APIError('El servidor devolvió una respuesta inválida.', 0, 'invalid_response')
    }
    throw new APIError('No se pudo conectar con el servidor. Intentá nuevamente.', 0, 'network_error')
  }
  const { data, error, response } = result
  if (!response.ok) {
    const body = error as ErrorBody | undefined
    throw new APIError(
      body?.error?.message ?? 'No se pudo completar la solicitud.',
      response.status,
      body?.error?.code,
    )
  }
  if (data && typeof data === 'object' && 'csrf_token' in data) {
    csrfToken = String((data as { csrf_token: string }).csrf_token)
  }
  return data as T
}

const id = (value: number) => ({ params: { path: { identifier: value } } })

export const api = {
  session: () => call(http.GET('/api/session')),
  login: (body: Schemas['LoginIn']) => call(http.POST('/api/login', { body })),
  logout: () => call(http.POST('/api/logout', { body: {} as never })),
  changePassword: (body: Schemas['PasswordIn']) => call(http.PUT('/api/password', { body })),
  catalogs: () => call(http.GET('/api/catalogos')),

  projects: (query: { estado?: string; responsable?: string }) =>
    call(http.GET('/api/proyectos', { params: { query } })),
  project: (identifier: number) => call(http.GET('/api/proyectos/{identifier}', id(identifier))),
  saveProject: (body: Schemas['ProyectoIn'], identifier?: number) =>
    identifier
      ? call(http.PUT('/api/proyectos/{identifier}', { ...id(identifier), body }))
      : call(http.POST('/api/proyectos', { body })),
  deleteProject: (identifier: number) =>
    call(http.DELETE('/api/proyectos/{identifier}', { ...id(identifier), body: {} as never })),

  tasks: (project: number) => call(http.GET('/api/proyectos/{identifier}/tareas', id(project))),
  task: (identifier: number) => call(http.GET('/api/tareas/{identifier}', id(identifier))),
  createTask: (project: number, body: Schemas['TareaIn']) =>
    call(http.POST('/api/proyectos/{identifier}/tareas', { ...id(project), body })),
  updateTask: (identifier: number, body: Schemas['TareaIn']) =>
    call(http.PUT('/api/tareas/{identifier}', { ...id(identifier), body })),
  deleteTask: (identifier: number) =>
    call(http.DELETE('/api/tareas/{identifier}', { ...id(identifier), body: {} as never })),

  consumptions: () => call(http.GET('/api/consumos')),
  consumption: (identifier: number) => call(http.GET('/api/consumos/{identifier}', id(identifier))),
  saveConsumption: (body: Schemas['ConsumoIn'], identifier?: number) =>
    identifier
      ? call(http.PUT('/api/consumos/{identifier}', { ...id(identifier), body }))
      : call(http.POST('/api/consumos', { body })),
  deleteConsumption: (identifier: number) =>
    call(http.DELETE('/api/consumos/{identifier}', { ...id(identifier), body: {} as never })),

  resources: () => call(http.GET('/api/recursos')),
  resource: (identifier: number) => call(http.GET('/api/recursos/{identifier}', id(identifier))),
  saveResource: (body: Schemas['RecursoIn'], identifier?: number) =>
    identifier
      ? call(http.PUT('/api/recursos/{identifier}', { ...id(identifier), body }))
      : call(http.POST('/api/recursos', { body })),
  deleteResource: (identifier: number) =>
    call(http.DELETE('/api/recursos/{identifier}', { ...id(identifier), body: {} as never })),

  roles: () => call(http.GET('/api/roles')),
  role: (identifier: number) => call(http.GET('/api/roles/{identifier}', id(identifier))),
  saveRole: (body: Schemas['RolIn'], identifier?: number) =>
    identifier
      ? call(http.PUT('/api/roles/{identifier}', { ...id(identifier), body }))
      : call(http.POST('/api/roles', { body })),
  deleteRole: (identifier: number) =>
    call(http.DELETE('/api/roles/{identifier}', { ...id(identifier), body: {} as never })),
}
