import { describe, expect, it } from 'vitest'
import type { Project, User } from '@/api/client'
import { availableEntities, MAX_UPLOAD_BYTES, MAX_UPLOAD_MESSAGE, tooLarge } from '@/bulk'

const user = (over: Partial<User>) =>
  ({ recurso_id: 2, recurso_nombre: 'ana', es_admin: false, debe_cambiar_password: false, ...over }) as User
const project = (owner_id: number) => ({ proyecto_id: 1, owner_id }) as Project

describe('availableEntities', () => {
  it('offers everything to admins in dependency order', () => {
    expect(availableEntities(user({ es_admin: true }), []).map((e) => e.key)).toEqual([
      'roles',
      'recursos',
      'proyectos',
      'tareas',
      'consumos',
    ])
  })
  it('offers consumos to everyone and tareas only to project owners', () => {
    expect(availableEntities(user({}), [project(9)]).map((e) => e.key)).toEqual(['consumos'])
    expect(availableEntities(user({}), [project(2)]).map((e) => e.key)).toEqual(['tareas', 'consumos'])
  })
})

describe('tooLarge', () => {
  it('allows files up to 5 MiB and rejects anything bigger', () => {
    expect(MAX_UPLOAD_BYTES).toBe(5 * 1024 * 1024)
    expect(tooLarge({ size: MAX_UPLOAD_BYTES })).toBe(false)
    expect(tooLarge({ size: MAX_UPLOAD_BYTES + 1 })).toBe(true)
    expect(MAX_UPLOAD_MESSAGE).toContain('5 MiB')
  })
})
