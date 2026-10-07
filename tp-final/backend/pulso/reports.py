"""Pure reporting calculations for the project dashboard (no database access).

Hours of a consumption are spread evenly over its inclusive date range, the same rule as
`frontend/src/projectHours.ts`, so the dashboard never disagrees with the cumulative chart.
"""

from collections import defaultdict
from collections.abc import Iterator
from datetime import date, timedelta

# Traffic-light thresholds for the efficiency / schedule indices (proposed defaults, adjustable).
INDEX_OK = 1.0
INDEX_WARNING = 0.85
RECENT_DAYS = 28
TOP_ACTIVITIES = 8
OTHER_ACTIVITIES = 'Otras'


def daily_hours(consumption: dict) -> Iterator[tuple[date, float]]:
    start, end = consumption['fecha_inicio'], consumption['fecha_fin']
    days = (end - start).days + 1
    for offset in range(days):
        yield start + timedelta(days=offset), consumption['horas_consumidas'] / days


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def index_state(value: float | None) -> str | None:
    if value is None:
        return None
    if value >= INDEX_OK:
        return 'bien'
    return 'atencion' if value >= INDEX_WARNING else 'critico'


def elapsed_days(project: dict, today: date) -> tuple[int, int]:
    duration = (project['fecha_fin'] - project['fecha_inicio']).days + 1
    return int(_clamp((today - project['fecha_inicio']).days + 1, 0, duration)), duration


def health(project: dict, today: date) -> dict:
    elapsed, duration = elapsed_days(project, today)
    time_pct = elapsed / duration * 100
    earned = project['porcentaje_avance'] / 100 * project['horas_requeridas']
    consumed = project['horas_consumidas']
    efficiency = earned / consumed if consumed > 0 else None
    schedule = project['porcentaje_avance'] / time_pct if time_pct > 0 else None
    return {
        'porcentaje_tiempo': time_pct,
        'porcentaje_consumo': project['porcentaje_consumo'],
        'porcentaje_avance': project['porcentaje_avance'],
        'horas_ganadas': earned,
        'indice_eficiencia': efficiency,
        'estado_eficiencia': index_state(efficiency),
        'indice_cronograma': schedule,
        'estado_cronograma': index_state(schedule),
    }


def _bucket_start(day: date, period: str) -> date:
    return day.replace(day=1) if period == 'mes' else day - timedelta(days=day.weekday())


def _next_bucket(start: date, period: str) -> date:
    if period == 'semana':
        return start + timedelta(days=7)
    return date(start.year + start.month // 12, start.month % 12 + 1, 1)


def periods(consumptions: list[dict], period: str) -> list[dict]:
    buckets: dict[date, dict] = {}
    for consumption in consumptions:
        for day, hours in daily_hours(consumption):
            bucket = buckets.setdefault(
                _bucket_start(day, period),
                {'horas': 0.0, 'por_rol': defaultdict(float), 'por_recurso': defaultdict(float)},
            )
            bucket['horas'] += hours
            bucket['por_rol'][consumption['rol_descripcion']] += hours
            bucket['por_recurso'][consumption['recurso_nombre']] += hours
    if not buckets:
        return []
    result = []
    current, last = min(buckets), max(buckets)
    while current <= last:
        bucket = buckets.get(current, {'horas': 0.0, 'por_rol': {}, 'por_recurso': {}})
        following = _next_bucket(current, period)
        result.append(
            {
                'desde': current,
                'hasta': following - timedelta(days=1),
                'horas': bucket['horas'],
                'por_rol': dict(bucket['por_rol']),
                'por_recurso': dict(bucket['por_recurso']),
            }
        )
        current = following
    return result


def pace(project: dict, consumptions: list[dict], today: date) -> dict:
    window_start = today - timedelta(days=RECENT_DAYS - 1)
    recent = 0.0
    to_date = 0.0
    for consumption in consumptions:
        for day, hours in daily_hours(consumption):
            if day <= today:
                to_date += hours
                if day >= window_start:
                    recent += hours
    first = min((c['fecha_inicio'] for c in consumptions), default=None)
    average = to_date / (max((today - first).days + 1, 7) / 7) if first and first <= today else 0.0
    remaining = (project['fecha_fin'] - today).days
    needed = None
    if remaining > 0 and project['saldo'] > 0:
        needed = project['saldo'] / (remaining / 7)
    return {
        'horas_semana_reciente': recent / (RECENT_DAYS / 7),
        'horas_semana_promedio': average,
        'horas_semana_necesarias': needed,
        'dias_restantes': max(remaining, 0),
    }


def execution(project: dict, consumptions: list[dict], today: date) -> dict:
    before = after = 0.0
    active: set[date] = set()
    for consumption in consumptions:
        for day, hours in daily_hours(consumption):
            before += hours if day < project['fecha_inicio'] else 0
            after += hours if day > project['fecha_fin'] else 0
            if day <= today:
                active.add(day)
    first = min((c['fecha_inicio'] for c in consumptions), default=None)
    return {
        'primer_consumo': first,
        'ultimo_consumo': max((c['fecha_fin'] for c in consumptions), default=None),
        'dias_desvio_inicio': (first - project['fecha_inicio']).days if first else None,
        'horas_antes_inicio': before,
        'horas_despues_fin': after,
        'dias_con_actividad': len(active),
        'dias_transcurridos': elapsed_days(project, today)[0],
    }


def task_health(tasks: list[dict], today: date) -> dict:
    overdue, late_start = [], []
    done = running = unassigned = 0
    weight = planned = real = 0.0
    for task in tasks:
        progress = task['porcentaje_avance']
        days = (task['fecha_fin'] - task['fecha_inicio']).days + 1
        weight += days
        planned += days * _clamp((today - task['fecha_inicio']).days + 1, 0, days) / days
        real += days * progress / 100
        unassigned += task['recurso_id'] is None
        if progress >= 100:
            done += 1
            continue
        running += progress > 0
        if task['fecha_fin'] < today:
            overdue.append(task)
        elif progress == 0 and task['fecha_inicio'] < today:
            late_start.append(task)
    return {
        'total': len(tasks),
        'completadas': done,
        'en_curso': running,
        'sin_recurso': unassigned,
        'vencidas': overdue,
        'sin_iniciar_atrasadas': late_start,
        'avance_planificado': planned / weight * 100 if weight else 0.0,
        'avance_real': real / weight * 100 if weight else 0.0,
    }


def _shares(totals: dict[str, float], whole: float, last: str | None = None) -> list[dict]:
    ordered = sorted(totals.items(), key=lambda item: (item[0] == last, -item[1], item[0]))
    return [
        {'nombre': name, 'horas': hours, 'porcentaje': hours / whole * 100 if whole else 0.0}
        for name, hours in ordered
    ]


def distribution(consumptions: list[dict]) -> dict:
    by_resource: dict[str, float] = defaultdict(float)
    by_role: dict[str, float] = defaultdict(float)
    by_activity: dict[str, float] = defaultdict(float)
    labels: dict[str, str] = {}
    for consumption in consumptions:
        hours = consumption['horas_consumidas']
        by_resource[consumption['recurso_nombre']] += hours
        by_role[consumption['rol_descripcion']] += hours
        key = consumption['tarea'].strip().lower()
        labels.setdefault(key, consumption['tarea'].strip())
        by_activity[key] += hours
    whole = sum(by_role.values())
    ranked = sorted(by_activity.items(), key=lambda item: (-item[1], item[0]))
    activities = {labels[key]: hours for key, hours in ranked[:TOP_ACTIVITIES]}
    rest = sum(hours for _, hours in ranked[TOP_ACTIVITIES:])
    if rest:
        activities[OTHER_ACTIVITIES] = rest
    return {
        'por_recurso': _shares(by_resource, whole),
        'por_rol': _shares(by_role, whole),
        'actividades': _shares(activities, whole, OTHER_ACTIVITIES),
    }
