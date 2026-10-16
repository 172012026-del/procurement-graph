"""Cross-platform project commands. Run from the repository root."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / 'demo/procurement'
BACKEND = PROJECT / 'backend'
FRONTEND = PROJECT / 'frontend'
PYTHON = PROJECT / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')


def run(command, env=None):
    subprocess.run([str(item) for item in command], cwd=ROOT, env=env, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['setup', 'api', 'web', 'test', 'doctor'])
    parser.add_argument('--with-tools', action='store_true')
    parser.add_argument('--require-tools', action='store_true')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int)
    parser.add_argument('--demo', action='store_true')
    args = parser.parse_args()
    if Path.cwd().resolve() != ROOT:
        parser.error('Run this command from the repository root')
    npm = shutil.which('npm.cmd' if os.name == 'nt' else 'npm')
    if args.mode in {'setup', 'web', 'test'} and not npm:
        parser.error('Node.js 22.12+ and npm are required')
    if args.mode == 'setup':
        if sys.version_info < (3, 12):
            parser.error('Python 3.12+ is required')
        if not (ROOT / '.env').exists():
            shutil.copyfile(ROOT / '.env.example', ROOT / '.env')
        if not PYTHON.exists():
            run([sys.executable, '-m', 'venv', PROJECT / '.venv'])
        run([PYTHON, '-m', 'pip', 'install', '-r', BACKEND / 'requirements.txt'])
        run([npm, '--prefix', FRONTEND, 'ci', '--no-fund', '--no-audit'])
        if args.with_tools:
            run([PYTHON, ROOT / 'scripts/install_local_tools.py'])
        run([PYTHON, ROOT / 'scripts/doctor.py', *(['--require-tools'] if args.with_tools else [])])
        return
    if args.mode != 'web' and not PYTHON.exists():
        parser.error('Run setup first')
    env = {**os.environ, 'PYTHONPATH': str(BACKEND), 'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONIOENCODING': 'utf-8'}
    if args.mode == 'api':
        if args.demo:
            env['DEMO_SEED'] = 'true'
        run([PYTHON, '-m', 'uvicorn', 'app.main:app', '--app-dir', BACKEND, '--host', args.host,
             '--port', args.port or 8000, '--workers', '1'], env)
    elif args.mode == 'web':
        run([npm, '--prefix', FRONTEND, 'run', 'dev', '--', '--host', args.host, '--port', args.port or 5173], env)
    elif args.mode == 'test':
        run([PYTHON, '-m', 'pytest', BACKEND / 'tests', '-q', '-c', BACKEND / 'pytest.ini',
             '-p', 'no:cacheprovider', '--basetemp', BACKEND / '.test-work/tmp'], env)
        run([npm, '--prefix', FRONTEND, 'run', 'build'], env)
    else:
        run([PYTHON, ROOT / 'scripts/doctor.py', *(['--require-tools'] if args.require_tools else [])], env)


if __name__ == '__main__':
    try:
        main()
    except subprocess.CalledProcessError as error:
        raise SystemExit(error.returncode)
