#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Levanta el entorno de desarrollo local con un solo comando.

Uso (desde tp-final/):

    uv run scripts/dev.py [--reinstall] [--down] [--skip-compose]

Esto es solo un wrapper de los pasos documentados en README.md ("Desarrollo
local"): no cambia cómo corre nada, encadena los mismos comandos como
subprocesos:

    <docker|podman> compose up -d db mailpit
    (cd backend && uv run python -m pulso.cli init-db)
    (cd backend && uv run uvicorn pulso.asgi:app --reload --port 5000)  &
    (cd frontend && npm install && npm run dev)                        &

Si algo falla, se puede seguir el camino manual del README para aislar el
problema; este script no hace nada que esos comandos no hagan.
"""

import argparse
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # tp-final/
BACKEND = ROOT / 'backend'
FRONTEND = ROOT / 'frontend'
DB_HOST, DB_PORT = '127.0.0.1', 5432
DB_WAIT_TIMEOUT = 60  # segundos


class Fail(SystemExit):
    """Sale con un mensaje legible, sin traceback."""


def die(msg: str) -> None:
    raise Fail(f'\n✗ {msg}\n')


class Stop(Exception):
    """Señal interna: pedido de apagado (Ctrl+C o SIGTERM)."""


def check_prereqs() -> tuple[str, str]:
    """uv es un dado (el script corre bajo él). Node/npm se verifican acá."""
    node = shutil.which('node')
    npm = shutil.which('npm')
    if node is None or npm is None:
        die(
            'Node.js 22+ no encontrado en el PATH. Instalalo desde '
            'https://nodejs.org/ (o con nvm/fnm) y volvé a intentar.'
        )
    return node, npm


def detect_compose() -> list[str]:
    """Devuelve el argv base de compose, probando docker y podman en orden."""
    candidates = [['docker', 'compose'], ['podman-compose'], ['podman', 'compose']]
    for cmd in candidates:
        try:
            subprocess.run([*cmd, 'version'], cwd=ROOT, capture_output=True, timeout=10, check=True)
            return cmd
        except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            continue
    die(
        'No se encontró Docker Compose ni Podman Compose. Instalá Docker '
        'Desktop (Windows/Mac) o docker-compose-plugin/podman-compose (Linux).'
    )


def compose_up(compose_cmd: list[str]) -> None:
    print(f"[dev] {' '.join(compose_cmd)} up -d db mailpit")
    subprocess.run([*compose_cmd, 'up', '-d', 'db', 'mailpit'], cwd=ROOT, check=True)


def wait_for_db(timeout: int = DB_WAIT_TIMEOUT) -> None:
    print(f'[dev] esperando Postgres en {DB_HOST}:{DB_PORT} ...')
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((DB_HOST, DB_PORT), timeout=1):
                print('[dev] Postgres listo.')
                return
        except OSError:
            time.sleep(0.5)
    die(f'Postgres no respondió en {DB_HOST}:{DB_PORT} después de {timeout}s. Revisá los logs de "db".')


def run_init_db() -> None:
    print('[dev] uv run python -m pulso.cli init-db')
    result = subprocess.run(['uv', 'run', 'python', '-m', 'pulso.cli', 'init-db'], cwd=BACKEND)
    if result.returncode != 0:
        die('init-db falló. Revisá el mensaje de arriba.')


def maybe_npm_install(npm: str, force: bool) -> None:
    if not force and (FRONTEND / 'node_modules').is_dir():
        print('[dev] frontend/node_modules ya existe, salteando npm install (usá --reinstall para forzar).')
        return
    print('[dev] npm install')
    subprocess.run([npm, 'install'], cwd=FRONTEND, check=True)


def stream(pipe, prefix: str) -> None:
    for raw_line in iter(pipe.readline, b''):
        sys.stdout.write(f'[{prefix}] {raw_line.decode(errors="replace")}')
    pipe.close()


def spawn(cmd: list[str], cwd: Path, prefix: str) -> subprocess.Popen:
    kwargs: dict = dict(cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if sys.platform == 'win32':
        kwargs['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs['start_new_session'] = True  # grupo de procesos propio
    proc = subprocess.Popen(cmd, **kwargs)
    thread = threading.Thread(target=stream, args=(proc.stdout, prefix), daemon=True)
    thread.start()
    return proc


def terminate(proc: subprocess.Popen, name: str) -> None:
    if proc.poll() is not None:
        return
    print(f'[dev] deteniendo {name}...')
    try:
        if sys.platform == 'win32':
            proc.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            proc.terminate()
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


def _handle_sigterm(signum, frame) -> None:
    raise Stop


def main() -> None:
    # Sin esto, los print() de este script (block-buffered al no ser una
    # terminal) aparecen mezclados fuera de orden con la salida de los
    # subprocesos, que escriben directo al fd heredado.
    sys.stdout.reconfigure(line_buffering=True)
    if sys.platform != 'win32':
        signal.signal(signal.SIGTERM, _handle_sigterm)

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--reinstall', action='store_true', help='forzar npm install aunque node_modules exista')
    parser.add_argument('--down', action='store_true', help='al salir, además bajar db/mailpit con compose down')
    parser.add_argument(
        '--skip-compose', action='store_true', help='no tocar contenedores; asume que db/mailpit ya están arriba'
    )
    args = parser.parse_args()

    _node, npm = check_prereqs()

    compose_cmd = None
    if not args.skip_compose:
        compose_cmd = detect_compose()
        compose_up(compose_cmd)
    wait_for_db()

    run_init_db()
    maybe_npm_install(npm, force=args.reinstall)

    api = spawn(['uv', 'run', 'uvicorn', 'pulso.asgi:app', '--reload', '--port', '5000'], BACKEND, 'api')
    web = spawn([npm, 'run', 'dev'], FRONTEND, 'web')

    print('\n[dev] API en http://127.0.0.1:5000 — Web en http://127.0.0.1:5173 — Ctrl+C para detener\n')

    try:
        while True:
            if api.poll() is not None:
                die('El proceso de la API terminó inesperadamente.')
            if web.poll() is not None:
                die('El proceso del frontend terminó inesperadamente.')
            time.sleep(0.5)
    except (KeyboardInterrupt, Stop):
        print('\n[dev] Cerrando...')
    finally:
        terminate(api, 'api')
        terminate(web, 'web')
        if args.down and compose_cmd:
            print(f"[dev] {' '.join(compose_cmd)} down")
            subprocess.run([*compose_cmd, 'down'], cwd=ROOT)
        else:
            print('[dev] db/mailpit siguen corriendo (usá --down la próxima vez, o pará con "compose down" a mano).')


if __name__ == '__main__':
    main()
