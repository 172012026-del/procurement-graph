"""Repeatable parser checks on provided data. No model calls or business database writes."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime
import json
import logging
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT/'demo/procurement/backend'
sys.path.insert(0,str(BACKEND))
sys.dont_write_bytecode = True
os.environ['DEEPSEEK_API_KEY'] = ''
os.environ['DEMO_SEED'] = 'false'
os.environ['NEO4J_URI'] = ''
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
os.environ.setdefault('UPLOAD_DIR',str(ROOT/'.cache'/'checks'/'uploads'))

from app.config import settings
from app.ingestion import local_groups
from app.parsers import archive_name,detect_type,expand_archives,parse_file,seven_zip


class ReaderWarnings(logging.Handler):
    def __init__(self):
        super().__init__(); self.count = 0
    def emit(self,record):
        self.count += 1


def check(all_html: bool, attachments: bool) -> dict:
    started = time.perf_counter()
    source = settings.official_data_dir
    report = {'checked_at':datetime.now().astimezone().isoformat(),'model_calls':0,'writes_to_business_db':False,
        'capabilities':{'7zip':bool(seven_zip()),'legacy_doc':bool(shutil.which('antiword') or shutil.which('libreoffice')),
                        'ocr':bool(shutil.which('tesseract'))},'html':[],'attachments':[],
        'scope':'解析可读性检查，不是字段准确率、官方得分或全流程性能测试'}
    groups = local_groups()
    report['input'] = {'notices':len(groups),'with_attachment_zip':sum(len(g)>1 for g in groups)}
    if all_html:
        for group in groups:
            before = time.perf_counter()
            try:
                text = parse_file(group[0])
                row = {'uuid':group[0].stem,'status':'readable','characters':len(text)}
            except Exception as exc:
                row = {'uuid':group[0].stem,'status':'failed','error':str(exc)[:200]}
            row['seconds'] = round(time.perf_counter()-before,4)
            report['html'].append(row)
    if attachments:
        index_dir = source/'indexes'
        with (index_dir/'attachment-signatures.csv').open(encoding='utf-8-sig') as f:
            index = list(csv.DictReader(f))
        old_samples = json.loads((index_dir/'attachment-samples.json').read_text('utf-8'))['checks']
        selected = [next(r for r in index if r['uuid']==s['uuid'] and r['member']==s['member']) for s in old_samples]
        # Include each real format and representative disguised files. Do not label every HTML mismatch corrupt.
        buckets = {}
        for row in index:
            key = (row['extension'],row['detected_header'])
            if key not in buckets and int(row['bytes']) <= 8*1024**2:
                buckets[key] = row
        selected += list(buckets.values())
        selected = list({(r['uuid'],r['member']):r for r in selected}.values())
        warning_handler = ReaderWarnings()
        reader_logger = logging.getLogger('pypdf'); previous_handlers = reader_logger.handlers[:]
        reader_logger.handlers = [warning_handler]; reader_logger.propagate = False
        temp_root = ROOT/'.cache'/'checks'
        temp_root.mkdir(parents=True,exist_ok=True)
        settings.upload_dir.mkdir(parents=True,exist_ok=True)
        try:
            with tempfile.TemporaryDirectory(prefix='parser-sample-',dir=temp_root) as temporary:
                scratch = Path(temporary)
                for number,row in enumerate(selected):
                    before = time.perf_counter(); warning_handler.count = 0
                    result = {'uuid':row['uuid'],'member':row['member'],'extension':row['extension'],
                              'indexed_type':row['detected_header'],'bytes':int(row['bytes'])}
                    try:
                        with zipfile.ZipFile(source/'file'/f"{row['uuid']}.zip") as archive:
                            member = next(info for info in archive.infolist() if archive_name(info.filename)==row['member'] or info.filename==row['member'])
                            if member.file_size>8*1024**2:
                                raise ValueError('抽样文件超过8MiB，不在本检查范围')
                            target = scratch/f'{number}{Path(row["member"]).suffix}'
                            target.write_bytes(archive.read(member))
                        kind = detect_type(target); result['detected_type'] = kind
                        if kind in {'.zip','.rar','.7z'}:
                            issues = []
                            files = expand_archives([target],scratch/f'expanded-{number}',issues)
                            result.update(status='archive_expanded' if files and not issues else 'needs_attention',
                                          child_files=len(files),issues=issues[:10])
                        else:
                            text = parse_file(target)
                            result.update(status='readable',characters=len(text))
                    except Exception as exc:
                        result.update(status='needs_attention',error=f'{type(exc).__name__}: {str(exc)[:220]}')
                    result['reader_warnings'] = warning_handler.count
                    result['seconds'] = round(time.perf_counter()-before,4)
                    report['attachments'].append(result)
        finally:
            reader_logger.handlers = previous_handlers; reader_logger.propagate = True
    report['html_statuses'] = dict(Counter(r['status'] for r in report['html']))
    report['attachment_statuses'] = dict(Counter(r['status'] for r in report['attachments']))
    report['elapsed_seconds'] = round(time.perf_counter()-started,3)
    return report


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--all-html',action='store_true')
    parser.add_argument('--sample-attachments',action='store_true')
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    report = check(args.all_html,args.sample_attachments)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:report[k] for k in ('input','html_statuses','attachment_statuses','capabilities','elapsed_seconds')},ensure_ascii=False))
