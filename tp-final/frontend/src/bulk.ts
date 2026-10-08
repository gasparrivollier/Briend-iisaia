import type { Project, User } from '@/api/client'

export type BulkKey = 'roles' | 'recursos' | 'proyectos' | 'tareas' | 'consumos'
export type BulkEntity = { key: BulkKey; label: string; columns: string }

export const ACCEPT = '.csv,.txt,.xlsx'
export const MAX_UPLOAD_BYTES = 5 * 1024 * 1024
export const MAX_UPLOAD_MESSAGE = 'El archivo supera el tamaño máximo permitido (5 MiB).'
export const tooLarge = (file: { size: number }) => file.size > MAX_UPLOAD_BYTES

// Dependency order: a file cannot reference rows created by the same upload.
const ENTITIES: BulkEntity[] = [
  { key: 'roles', label: 'Roles', columns: 'rol_descripcion' },
  { key: 'recursos', label: 'Recursos', columns: 'recurso_nombre, email, es_admin, password (mín. 8 caracteres)' },
  {
    key: 'proyectos',
    label: 'Proyectos',
    columns:
      'proyecto_nombre, fecha_inicio, fecha_fin, horas_requeridas, owner (nombre del recurso), proyect_status, porcentaje_avance',
  },
  {
    key: 'tareas',
    label: 'Tareas',
    columns: 'proyecto (o proyecto_id), tarea_nombre, fecha_inicio, fecha_fin, porcentaje_avance, recurso',
  },
  {
    key: 'consumos',
    label: 'Consumos',
    columns: 'proyecto (o proyecto_id), recurso, rol, fecha_inicio, fecha_fin, horas_consumidas, tarea',
  },
]

/** What the user may load: admins everything, owners their tasks, everyone their own consumptions. */
export function availableEntities(user: User, projects: Project[]): BulkEntity[] {
  if (user.es_admin) return ENTITIES
  const ownsProject = projects.some((p) => p.owner_id === user.recurso_id)
  return ENTITIES.filter((e) => e.key === 'consumos' || (e.key === 'tareas' && ownsProject))
}
