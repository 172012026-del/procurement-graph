"""Check portable tools against source-anchored official attachment samples."""
from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'results/parser-tools'
OUTPUT.mkdir(parents=True, exist_ok=True)
os.environ['UPLOAD_DIR'] = str(OUTPUT / 'work')
sys.path.insert(0, str(ROOT / 'demo/procurement/backend'))

from app.config import settings
from app.parsers import detect_type, expand_archives, office_tool, parse_file, seven_zip


def main():
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    source_rows = list(csv.DictReader((ROOT/'data/official-benchmark/indexes/attachment-members.csv').open(encoding='utf-8-sig')))
    selected = []
    for extension in ('.doc', '.wps', '.rar', '.7z', '.docx'):
        candidates = [r for r in source_rows if r['extension'] == extension and int(r['bytes']) > 5000]
        signatures = {'.doc': b'\xd0\xcf', '.wps': b'\xd0\xcf', '.rar': b'Rar!', '.7z': b'7z', '.docx': b'PK'}
        for row in sorted(candidates, key=lambda r: int(r['bytes'])):
            with zipfile.ZipFile(ROOT/row['package_path']) as archive:
                with archive.open(row['member']) as member:
                    head = member.read(16)
            if head.startswith(signatures[extension]):
                selected.append((extension, row))
                break
    scan = next(r for r in source_rows if r['uuid'] == 't20260510_26542466' and r['member'] == '评审情况.pdf')
    selected.append(('.pdf', scan))
    report = {'scope': 'real official samples, not full-corpus accuracy', 'tools': {'office': office_tool(), 'sevenzip': seven_zip()}, 'samples': []}
    for index, (extension, source) in enumerate(selected, 1):
        path = OUTPUT / f'sample-{index}{extension}'
        with zipfile.ZipFile(ROOT/source['package_path']) as archive:
            data = archive.read(source['member'])
        path.write_bytes(data)
        record = {'notice_uuid': source['uuid'], 'member': source['member'], 'saved_file': path.name,
                  'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}
        started = time.perf_counter()
        try:
            record['detected_type'] = detect_type(path)
            errors = []
            files = expand_archives([path], OUTPUT/f'expanded-{index}', errors) if extension in {'.rar', '.7z'} else [path]
            details = []
            for file in files:
                try:
                    text = parse_file(file)
                    details.append({'file': file.name, 'characters': len(text), 'preview': text[:300]})
                except Exception as exc:
                    errors.append(f'{file.name}: {type(exc).__name__}: {str(exc)[:160]}')
            record.update(status='complete' if not errors else 'partial', files=details, errors=errors)
        except Exception as exc:
            record.update(status='failed', error=f'{type(exc).__name__}: {str(exc)[:200]}')
        record['elapsed_seconds'] = round(time.perf_counter()-started, 4)
        report['samples'].append(record)
        (OUTPUT/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(record, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
