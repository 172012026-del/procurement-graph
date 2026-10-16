"""Check local prerequisites without model requests or credential output."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'demo/procurement/backend'))


def inspect(require_tools=False, require_competition=False):
    checks = []
    def add(name, passed, required=True, detail=''):
        checks.append({'name': name, 'passed': bool(passed), 'required': required, 'detail': detail})
    add('python', sys.version_info >= (3, 12), detail=sys.version.split()[0])
    for name in ['fastapi', 'httpx', 'docx', 'openpyxl', 'pypdf', 'rapidocr', 'neo4j', 'dotenv']:
        add('python:' + name, importlib.util.find_spec(name) is not None)
    node = shutil.which('node')
    try:
        version = subprocess.run([node, '--version'], capture_output=True, text=True, check=True).stdout.strip()
        numbers = tuple(int(part) for part in version.lstrip('v').split('.')[:2])
        add('node', numbers >= (22, 12), detail=version)
    except (OSError, TypeError, ValueError, subprocess.CalledProcessError):
        add('node', False, detail='Install Node.js 22.12+')
    sample = ROOT / 'demo/procurement/data/demo'
    try:
        manifest = json.loads((sample / 'manifest.json').read_text('utf-8'))
        add('sample:source', all((sample / 'html' / name).is_file() and hashlib.sha256((sample / 'html' / name).read_bytes()).hexdigest() == digest
                                 for name, digest in manifest['source_files_sha256'].items()))
        add('sample:cache', all((sample / 'cache' / name).is_file() for name in manifest['response_cache_files']))
        add('sample:results', (sample / 'sample-results.jsonl').is_file() and (sample / 'sample-announcements.zip').is_file())
    except (OSError, ValueError, KeyError):
        add('sample:manifest', False)
    try:
        from app.parsers import office_tool, seven_zip
        from app.ocr import available
        from app.config import settings
        from app.model_settings import current_settings
        settings = current_settings(settings)
        add('tools:office', bool(office_tool() or shutil.which('antiword')), require_tools, 'LibreOffice or antiword')
        add('tools:archives', bool(seven_zip()), require_tools, '7z or 7zz')
        add('tools:ocr', available(), require_tools, 'RapidOCR or Tesseract')
        profile = Path(settings.model_profile_path)
        metadata = json.loads(profile.read_text('utf-8')) if profile.is_file() else {}
        required = ['model_id', 'version', 'parameter_scale', 'resource_origin']
        evidence = metadata.get('resource_evidence') or metadata.get('organizer_evidence')
        stage = metadata.get('competition_stage', 'preliminary')
        policy = bool(metadata.get('institution_model_policy')) if stage == 'preliminary' else (
            metadata.get('resource_origin') == 'organizer' or metadata.get('resource_origin') == 'self-hosted-finetuned')
        add('competition:model-metadata', all(metadata.get(key) for key in required) and evidence and policy,
            require_competition, 'Check preliminary institutional policy or final resource evidence; no inference performed')
        add('competition:review-access', bool(settings.api_token), require_competition, 'Private application access token')
        configuration = {'model_network_enabled': settings.model_network_enabled,
                         'model_key_configured': bool(settings.deepseek_api_key),
                         'neo4j_configured': bool(settings.neo4j_uri)}
    except ImportError:
        add('application:dependencies', False)
        configuration = {}
    return {'passed': all(item['passed'] for item in checks if item['required']), 'checks': checks,
            'configuration': configuration, 'model_requests': 0}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--require-tools', action='store_true')
    parser.add_argument('--require-competition', action='store_true')
    args = parser.parse_args()
    report = inspect(args.require_tools, args.require_competition)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report['passed'] else 1)
