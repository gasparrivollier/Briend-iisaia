import { expect, type Page, test } from '@playwright/test'

// One ordered story over a fresh database (start-api.sh recreates it on every run).
test.describe.configure({ mode: 'serial' })

async function login(page: Page, name: string, password: string) {
  await page.goto('/login')
  await page.getByLabel('Usuario').fill(name)
  await page.getByLabel('Contraseña', { exact: true }).fill(password)
  await page.getByRole('button', { name: 'Ingresar' }).click()
  await page.waitForURL((url) => url.pathname !== '/login')
}

test('forced password change on first admin login', async ({ page }) => {
  await login(page, 'admin', 'Proyecto1')
  await expect(page).toHaveURL(/\/password$/)
  await expect(page.getByText('reemplazá tu contraseña inicial')).toBeVisible()
  await page.goto('/proyectos') // blocked until the password is changed
  await expect(page).toHaveURL(/\/password$/)
  await page.getByLabel('Contraseña actual').fill('Proyecto1')
  await page.getByLabel('Nueva contraseña', { exact: true }).fill('AdminNueva1')
  await page.getByLabel('Confirmar nueva contraseña').fill('AdminNueva1')
  await page.getByRole('button', { name: 'Guardar contraseña' }).click()
  await expect(page).toHaveURL(/\/proyectos$/)
  await expect(page.getByText('Contraseña actualizada.')).toBeVisible()
})

test('admin creates a user, a role and a project', async ({ page }) => {
  await login(page, 'admin', 'AdminNueva1')
  await page.getByRole('link', { name: 'Recursos' }).click()
  await page.getByRole('link', { name: '+ Nuevo recurso' }).click()
  await page.getByLabel('Nombre de usuario').fill('ana')
  await page.getByLabel('Email (opcional)').fill('ana@example.com')
  await page.getByLabel('Contraseña inicial').fill('Inicial123')
  await page.getByRole('button', { name: 'Guardar' }).click()
  await expect(page.getByRole('cell', { name: 'ana', exact: true })).toBeVisible()

  await page.getByRole('link', { name: 'Roles' }).click()
  await page.getByRole('link', { name: '+ Nuevo rol' }).click()
  await page.getByLabel('Descripción del rol').fill('Analista')
  await page.getByRole('button', { name: 'Guardar' }).click()
  await expect(page.getByRole('cell', { name: 'Analista' })).toBeVisible()

  await page.getByRole('link', { name: 'Proyectos', exact: true }).click()
  await page.getByRole('link', { name: '+ Nuevo proyecto' }).click()
  await page.getByLabel('Nombre del proyecto').fill('Portal <b>clientes</b>')
  await page.getByLabel('Fecha de inicio').fill('2026-09-01')
  await page.getByLabel('Fecha de fin prevista').fill('2026-09-30')
  await page.getByLabel('Horas requeridas').fill('20')
  await page.getByLabel('Avance real (%)').fill('40')
  await page.getByLabel('Responsable').selectOption({ label: 'ana' })
  await page.getByLabel('Estado').selectOption('en curso')
  await page.getByRole('button', { name: 'Guardar' }).click()
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Portal <b>clientes</b>') // escaped
  await expect(page.getByText('ana · 2026-09-01 → 2026-09-30 · en curso')).toBeVisible()
})

test('plain user logs hours; invalid input keeps the form', async ({ page }) => {
  await login(page, 'ana', 'Inicial123')
  await page.getByLabel('Contraseña actual').fill('Inicial123')
  await page.getByLabel('Nueva contraseña', { exact: true }).fill('AnaPropia12')
  await page.getByLabel('Confirmar nueva contraseña').fill('AnaPropia12')
  await page.getByRole('button', { name: 'Guardar contraseña' }).click()
  await expect(page).toHaveURL(/\/proyectos$/)
  await expect(page.getByRole('link', { name: 'Recursos' })).toHaveCount(0) // admin-only nav hidden

  await page.getByRole('link', { name: 'Ver proyecto →' }).click()
  await page.getByRole('link', { name: '+ Registrar consumo' }).click()
  await expect(page.getByText('Recurso: ana')).toBeVisible()
  await page.getByLabel('Rol desempeñado').selectOption({ label: 'Analista' })
  await page.getByLabel('Tarea realizada').fill('Relevamiento')
  await page.getByLabel('Fecha de inicio').fill('2026-10-02')
  await page.getByLabel('Fecha de fin').fill('2026-10-01')
  await page.getByLabel('Horas consumidas').fill('25.5')
  await page.getByRole('button', { name: 'Guardar' }).click()
  await expect(page.getByRole('alert')).toHaveText('La fecha de fin no puede ser anterior al inicio.')
  await expect(page.getByLabel('Tarea realizada')).toHaveValue('Relevamiento') // input preserved

  await page.getByLabel('Fecha de fin').fill('2026-10-03')
  await page.getByRole('button', { name: 'Guardar' }).click()
  await expect(page.getByText('Cambios guardados.')).toBeVisible()
  // 25,5 h over 20 h: overrun of 5,5 h; manual progress unchanged.
  await expect(page.getByText('-5,5 / 5,5')).toBeVisible()
  await expect(page.getByText('40 %').first()).toBeVisible()

  await page.goto('/recursos') // admin route: redirected
  await expect(page).toHaveURL(/\/proyectos$/)
  await page.getByRole('button', { name: 'Salir' }).click()
  await expect(page).toHaveURL(/\/login$/)
})

test('reloading a deep link keeps the session', async ({ page }) => {
  await login(page, 'admin', 'AdminNueva1')
  await page.goto('/proyectos/1')
  await page.reload()
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Portal <b>clientes</b>')
  page.once('dialog', (dialog) => dialog.accept())
  await page.getByRole('row', { name: /Relevamiento/ }).getByRole('button', { name: 'Eliminar' }).click()
  await expect(page.getByText('Registro eliminado.')).toBeVisible()
  await expect(page.getByText('Todavía no hay consumos registrados.')).toBeVisible()
})

test('project owner plans tasks on the Gantt', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  const puts: string[] = []
  page.on('request', (request) => request.method() === 'PUT' && puts.push(request.url()))
  await login(page, 'ana', 'AnaPropia12') // owner of project 1 (2026-09-01 → 2026-09-30)
  await page.goto('/proyectos/1')
  await expect(page.getByText('Todavía no hay tareas planificadas.')).toBeVisible()

  await page.getByRole('link', { name: '+ Nueva tarea' }).click()
  await page.getByLabel('Nombre de la tarea').fill('Diseño <i>UX</i> & R&D')
  await page.getByLabel('Fecha de inicio').fill('2026-09-01')
  await page.getByLabel('Fecha de fin').fill('2026-10-05') // outside the project
  await page.getByLabel('Responsable de la tarea').selectOption({ label: 'ana' })
  await page.getByRole('button', { name: 'Guardar' }).evaluate((b: HTMLButtonElement) => b.form!.noValidate = true)
  await page.getByRole('button', { name: 'Guardar' }).click()
  await expect(page.getByRole('alert')).toHaveText(
    'Las fechas de la tarea deben estar dentro de las del proyecto (2026-09-01 → 2026-09-30).',
  )
  await page.getByLabel('Fecha de fin').fill('2026-09-10')
  await page.getByRole('button', { name: 'Guardar' }).click()
  await expect(page).toHaveURL(/\/proyectos\/1$/)

  const gantt = page.getByTestId('gantt')
  await expect(gantt.locator('.bar-label', { hasText: 'Diseño <i>UX</i> & R&D' })).toBeVisible() // text, not markup
  await expect(gantt.locator('.bar-label i')).toHaveCount(0)
  await expect(page.getByRole('cell', { name: /Diseño <i>UX<\/i> & R&D/ })).toContainText('ana')

  // Drag the bar two days to the right (Day view: one column per day).
  await page.getByRole('button', { name: 'Día' }).click()
  const bar = gantt.locator('.bar-wrapper .bar').first()
  await bar.scrollIntoViewIfNeeded() // page.mouse does not scroll
  // frappe-gantt animates the bars after a scale change: wait until the geometry settles.
  let box = (await bar.boundingBox())!
  await expect(async () => {
    const previous = box
    await page.waitForTimeout(150)
    box = (await bar.boundingBox())!
    expect(box).toEqual(previous)
  }).toPass()
  const day = box.width / 10 // the bar spans 2026-09-01 → 2026-09-10
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2)
  await page.mouse.down()
  await page.mouse.move(box.x + box.width / 2 + day * 2, box.y + box.height / 2, { steps: 8 })
  await page.mouse.up()
  // frappe-gantt snaps the drag to whole days (the exact count depends on its offsetX math), so check
  // that the task moved forward, kept its 10 days, and the table shows what the API saved.
  const saved = page.getByRole('alert').filter({ hasText: 'Tarea reprogramada' })
  await expect(saved).toBeVisible()
  const [start, end] = (await saved.textContent())!.match(/\d{4}-\d{2}-\d{2}/g)!
  expect(start! > '2026-09-01').toBe(true)
  expect((Date.parse(end!) - Date.parse(start!)) / 86_400_000).toBe(9)
  await expect(page.getByRole('cell', { name: `${start} ${end}` })).toBeVisible()
  expect(puts).toHaveLength(1) // one request per drag, not one per day crossed

  // Dragging it before the project start is rejected by the API and the bar goes back.
  const settle = async () => {
    let last = (await bar.boundingBox())!
    await expect(async () => {
      const previous = last
      await page.waitForTimeout(150)
      last = (await bar.boundingBox())!
      expect(last).toEqual(previous)
    }).toPass()
    return last
  }
  const before = await settle()
  await page.mouse.move(before.x + before.width / 2, before.y + before.height / 2)
  await page.mouse.down()
  await page.mouse.move(before.x + before.width / 2 - day * 6, before.y + before.height / 2, { steps: 8 })
  await page.mouse.up()
  await expect(page.getByRole('alert')).toHaveText(
    'Las fechas de la tarea deben estar dentro de las del proyecto (2026-09-01 → 2026-09-30).',
  )
  await expect(page.getByRole('cell', { name: `${start} ${end}` })).toBeVisible()
  expect((await settle()).x).toBeCloseTo(before.x, 0)
  expect(puts).toHaveLength(2)

  // A deleted or unknown task shows an error instead of loading forever.
  await page.goto('/tareas/999/editar')
  await expect(page.getByText('No se pudo cargar la página')).toBeVisible()
  expect(errors).toEqual([])
})
