# Plan: Batch upload (carga masiva) for Pulso

## Context
`ESPECIFICACION.md` lists "cargas masivas por CSV, con vista previa de errores por fila" as the last pending item of Phase 5. Nothing exists yet: no parser, no multipart route, no `python-multipart`/`openpyxl`. The user wants a batch upload that accepts `.csv`, `.xlsx` and `.txt` for all five entities, with a mapped file layout per table.

Decisions already made with the user:
- Entities: Recursos, Roles, Proyectos, Tareas, Consumos. **One entity per upload** (user picks the entity).
- Formats: `.csv`, `.xlsx` (first sheet), `.txt` (delimited text, same parser as csv).
- Errors: **preview, then confirm** (preview writes nothing; confirm is all-or-nothing in one transaction).
- Approach: **stateless**. Preview and confirm both send the file; the server re-validates on confirm. No new table, no migration.
- References by **name with id fallback** (matching is trimmed and case-insensitive).
- Defaults accepted: existing permission matrix; no per-row emails; password column for Recursos; all-or-nothing confirm.

## Table / dictionary map (file layouts)
`*` = required. Headers are normalised (lowercase, accents and spaces stripped, `_` separator) and accept the aliases in parentheses. Extra columns are reported as a warning and ignored.

| Entity | Who may upload | Columns |
|---|---|---|
| Roles (`rol`) | admin | `rol_descripcion`* (`rol`, `descripcion`) |
| Recursos (`recurso`) | admin | `recurso_nombre`* (`nombre`), `email`, `es_admin` (si/no/true/false/1/0, default no), `password`* (>= 8 chars; user gets `debe_cambiar_password=true`) |
| Proyectos (`proyecto`) | admin | `proyecto_nombre`*, `fecha_inicio`*, `fecha_fin`*, `horas_requeridas`*, `owner` (recurso_nombre) or `owner_id`*, `proyect_status`* (one of `STATUSES`), `porcentaje_avance` (default 0) |
| Tareas (`tarea`) | admin, or owner of that project | `proyecto` (name) or `proyecto_id`*, `tarea_nombre`*, `fecha_inicio`*, `fecha_fin`*, `porcentaje_avance` (default 0), `recurso` (name, optional) or `recurso_id` |
| Consumos (`consumo`) | any user (non-admins always log as themselves; a `recurso` column that names someone else is a row error) | `proyecto` or `proyecto_id`*, `recurso` or `recurso_id` (admin only; required for admins), `rol` (rol_descripcion) or `rol_id`*, `fecha_inicio`*, `fecha_fin`*, `horas_consumidas`*, `tarea`* |

Dictionaries resolved from the file: `STATUSES` (models.py:20, case-sensitive exact match, after trim), `rol` and `recurso` by name (unique, case-insensitive), `proyecto` by name (**not unique**: ambiguous name becomes a row error asking for `proyecto_id`). Load order for a new environment: Roles, Recursos, Proyectos, Tareas, Consumos (a file cannot reference rows from the same upload, so parents must exist first).

## Design

### Parsing (`backend/pulso/bulk/parsing.py`, pure, no DB)
- Detect format from the extension and verify content (xlsx is a zip; csv/txt is text). Anything else gives `400 formato_no_soportado`.
- csv/txt: decode `utf-8-sig`, fall back to `cp1252`; sniff the delimiter among `, ; \t |`; stdlib `csv`.
- xlsx: `openpyxl` `read_only=True, data_only=True`, first sheet only. `datetime` becomes `date`; integer-valued floats become `int` for id columns.
- Cell normalisation before validation: blank string becomes `None`; decimal comma `"1,5"` becomes `1.5` for numeric columns; date accepted as `YYYY-MM-DD` plus `DD/MM/YYYY` (converted to ISO so `iso_date` in `schemas.py` stays untouched); boolean words for `es_admin`.
- Limits: 5 MiB per file, 5000 data rows (200 for Recursos because argon2 hashing costs ~50 ms per row); header row required; empty files and duplicate headers are rejected.

### Entity specs (`backend/pulso/bulk/entities.py`)
One spec per entity: column aliases, required columns, a resolver that turns names into ids using maps preloaded once per upload (no per-row queries), and the existing Pydantic model (`RolIn`, `RecursoIn`, `ProyectoIn`, `TareaIn`, `ConsumoIn`) for field validation. Row validation order: normalise, Pydantic, reference resolution, permission, business rules. Errors are collected per row with `errors()` from Pydantic (not only the first error, unlike `main.py`'s handler).
Business rules reused, not copied: task dates inside the project dates (`tasks.py:396`), consumption `horas <= 12 * days` (in `ConsumoIn`), name uniqueness for Rol/Recurso (case-insensitive, checked against the DB and against earlier rows of the same file).
Warnings (do not block): exact-duplicate Consumo against existing rows or earlier rows in the file; ignored extra columns.

### Service and endpoint (`backend/pulso/bulk/service.py`, `routers/bulk.py`)
- `POST /api/carga-masiva/{entidad}?confirmar=false|true`, `multipart/form-data` with one `archivo` field.
- `GET /api/carga-masiva/{entidad}/plantilla.csv`: header row and one example row (GET, so no CSRF or CSP issue).
- Response: `{entidad, total, validas, errores: [{fila, campo, mensaje}], advertencias: [...], creadas}`. Preview (`confirmar=false`) never writes. `confirmar=true` re-validates; if any error remains it returns `422`-style `carga_invalida` and writes nothing; otherwise it inserts all rows in one transaction (`db.begin()`, bulk `add_all`) and returns `creadas`.
- Entity-level permission is a dependency like `require_admin` / `editable_project`, so it runs before parsing (403 beats 400). Tareas are checked per row (owner of that row's project).
- Side effects for Consumos: no per-row emails. After commit, one summary email per project owner, and the "horas excedidas" alert is evaluated once per project (sum before vs after the batch), reusing the logic in `consumptions.py:37-73` extracted into a shared helper. Extraction of the non-committing parts of the existing `apply` functions is the only change to existing router code.

### Guard, size limits and deploy
- `guard()` in `sessions.py:45-67` gets a variant for multipart: same 401, 403 `password_change_required` and CSRF checks, but it skips the 415 and JSON-object checks. The existing 415 test (form-encoded body) stays valid for every other route.
- `main.py:183-186` size middleware: a larger limit for the `/api/carga-masiva/` prefix (6 MiB), and read the body in a capped stream so a missing `Content-Length` cannot bypass it.
- `deploy/Caddyfile:181-183`: separate `request_body max_size 6MB` for `/api/carga-masiva/*`.
- New deps in `backend/pyproject.toml`: `python-multipart`, `openpyxl`; regenerate `uv.lock` (the Dockerfile uses it).

### Frontend
- Route `/carga-masiva` (`router.ts`, `meta.title`, not admin-only) and a link in `components/AppHeader.vue`. The entity selector only offers entities the user may load (users: Consumos; project owners: plus Tareas; admins: all).
- `views/BulkUploadView.vue` with steps: pick entity (template download link), pick file, **Vista previa** (summary counts plus a per-row error table), **Confirmar carga**. The file stays in component memory between the two calls. After confirm, invalidate all queries (as `composables/submit.ts` does).
- `api/client.ts`: multipart support. Pass `FormData` with `bodySerializer: (b) => b` so the browser sets the boundary; CSRF header is already added by `onRequest`. Handle a Caddy 413 (no JSON body) with a clear "archivo demasiado grande" message. Run `npm run gen:api`.

## Files
- New: `backend/pulso/bulk/{__init__,parsing,entities,service}.py`, `backend/pulso/routers/bulk.py`, `frontend/src/views/BulkUploadView.vue` (+ small preview table component), tests below.
- Modified: `main.py` (router, size limit), `sessions.py` (guard variant), `routers/consumptions.py` and `routers/tasks.py` (extract shared rule helpers), `deploy/Caddyfile`, `pyproject.toml`/`uv.lock`, `router.ts`, `AppHeader.vue`, `api/client.ts`, `api/schema.d.ts` (generated).
- Docs (Spanish): `docs/API.md` (multipart exception to "all mutations are JSON"), `ESPECIFICACION.md`, `README.md` permission matrix, `PLAN.md`, `VALIDACION.md`, and `tp-final/prompts.md` (mandatory log).

## Verification
- Backend (`cd backend && uv run pytest -q`, needs the dev Postgres): `tests/test_bulk_parsing.py` (encodings, delimiters, decimal comma, xlsx dates and ints, limits, bad formats) and `tests/test_bulk_api.py` (per entity: preview writes nothing, confirm inserts all, one bad row blocks the confirm, permissions 401/403/CSRF, ambiguous project name, in-file and DB duplicates, summary email once per project, exceeded-hours alert once). Needs a multipart helper, since `mutate()` always sends JSON. `uv run ruff check . && uv run ruff format --check .`.
- Frontend: Vitest for the client multipart path and router; `npm run gen:api` shows no drift; Playwright e2e: upload a Consumos csv, see the preview, fix one row, confirm.
- Manual: run the stack (`podman compose up -d db mailpit`, `uv run uvicorn ...`, `npm run dev`), upload one real `.csv`, `.xlsx` and `.txt` per entity in load order, and check the data and the Mailpit summary email.

## Out of scope
Multi-sheet xlsx, updates or upserts of existing rows, a single file mixing entities, background or async processing for very large files, exporting data.
