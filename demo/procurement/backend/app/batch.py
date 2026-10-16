"""Reproducible official-data processing and submission exports from the CLI."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
from pathlib import Path
import time
import uuid


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


async def execute(args) -> dict:
    # Corrupt PDFs can emit thousands of repeated recovery warnings. Parse
    # failures are still recorded per file; keep console output bounded.
    logging.getLogger('pypdf').setLevel(logging.ERROR)
    # Import only after CLI path overrides so a diagnostic database is isolated.
    from . import analytics
    from .config import settings
    from .model_settings import current_settings
    settings = current_settings(settings)
    from .database import init_db, rows
    from .exports import export_records, workbook_bytes
    from .ingestion import local_groups
    from .jobs import create_job, get_job, process_job, retry_job

    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if args.mode == 'extract' and not args.run_model:
        raise ValueError('真实抽取需要明确指定 --run-model；解析预检请使用 --mode parse-only')
    if args.mode == 'extract' and not settings.model_network_enabled:
        raise ValueError('模型网络调用已暂停；先确认样本和预算，不执行付费抽取')
    if args.mode == 'extract' and not settings.deepseek_api_key:
        raise ValueError('请先在前端连接设置或本机配置中保存可用的模型Key')
    init_db()
    if args.retry_job:
        original = get_job(args.retry_job)
        if not original or original.mode != args.mode:
            raise ValueError('重试批次模式不一致')
        state = retry_job(args.retry_job)
    else:
        ids = args.notice_id
        if args.manifest:
            manifest = json.loads(args.manifest.read_text('utf-8-sig'))
            ids = [x if isinstance(x, str) else x['notice_uuid'] for x in manifest.get('records', manifest.get('notices', []))] if isinstance(manifest, dict) else list(manifest)
        groups = local_groups(args.limit, ids or [])
        if args.announcement_only:
            groups = [[group[0]] for group in groups]
        if not groups:
            raise ValueError('没有匹配的官方公告')
        job_id = uuid.uuid4().hex
        state = create_job(job_id, [], settings.upload_dir / job_id, args.dataset, groups, args.mode)
    write_json(output / 'run-start.json', {'job_id': state.id, 'dataset_id': state.dataset_id,
        'mode': state.mode, 'started_at_epoch': time.time(), 'requested_model': settings.deepseek_model})
    task = asyncio.create_task(process_job(state.id))
    while not task.done():
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=20)
        except asyncio.TimeoutError:
            current = get_job(state.id)
            print(json.dumps({'job_id': current.id, 'status': current.status,
                'completed': current.completed, 'total': current.total,
                'succeeded': current.succeeded, 'partial': current.partial, 'failed': current.failed}, ensure_ascii=False), flush=True)
    await task
    state = get_job(state.id)
    docs = rows('SELECT notice_uuid,status,result_json,errors,elapsed_seconds FROM job_documents WHERE job_id=? ORDER BY notice_uuid', (state.id,))
    for doc in docs:
        doc['errors'] = json.loads(doc['errors'])
        raw_result = doc.pop('result_json')
        doc['result'] = json.loads(raw_result) if raw_result else None
    write_json(output / 'documents.json', docs)
    report = {'job': state.model_dump(), 'official_score': False,
              'source_scope': 'announcement-only' if args.announcement_only else 'announcement-and-attachments',
              'database_path': str(settings.database_path), 'output_directory': str(output),
              'scope': '本机实际批处理；不等同官方评分或官方机器验收'}
    if state.mode in {'extract','replay'}:
        records, notes = export_records(state.dataset_id, state.id)
        (output / 'predictions.jsonl').write_text(''.join(r.model_dump_json() + '\n' for r in records), encoding='utf-8')
        (output / 'procurement-tables.xlsx').write_bytes(workbook_bytes(records))
        write_json(output / 'quality-report.json', {'notes': notes, 'complete': state.failed == state.partial == 0 and state.succeeded == state.total})
        package_count = sum(len(r.package_records()) for r in records)
        write_json(output / 'relation-model.json', analytics.relationship_graph(max(package_count, 1), state.dataset_id))
        report['results'] = {'notices': len(records), 'packages': package_count,
            'items': sum(len(l.items) for r in records for l in r.package_records()),
            'bids': sum(len(l.bids) for r in records for l in r.package_records())}
    report['artifacts'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in output.iterdir() if p.is_file() and p.name != 'run-report.json'}
    write_json(output / 'run-report.json', report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('parse-only', 'extract', 'replay'), default='parse-only')
    parser.add_argument('--run-model', action='store_true')
    parser.add_argument('--strategy', choices=('schema', 'direct'), default='schema')
    parser.add_argument('--dataset', default='official')
    parser.add_argument('--limit', type=int)
    parser.add_argument('--notice-id', action='append', default=[])
    parser.add_argument('--announcement-only', action='store_true', help='For controlled announcement-only experiments, not full competition extraction')
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--retry-job')
    parser.add_argument('--database', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    os.environ['EXTRACTION_STRATEGY'] = args.strategy
    if args.limit is not None and args.limit < 1:
        parser.error('--limit must be positive')
    if args.database:
        os.environ['DATABASE_PATH'] = str(args.database.resolve())
        os.environ['UPLOAD_DIR'] = str(args.database.resolve().parent / 'work')
    try:
        report = asyncio.run(execute(args))
    except (ValueError, OSError) as exc:
        parser.exit(2, str(exc) + '\n')
    state = report['job']
    metrics = dict(state['metrics'])
    keys = metrics.pop('response_cache_keys', [])
    metrics['response_cache_key_count'] = len(keys)
    print(json.dumps({'job_id': state['id'], 'status': state['status'],
        'completed': state['completed'], 'total': state['total'], 'metrics': metrics,
        'results': report.get('results', {})}, ensure_ascii=False), flush=True)
    if state['status'] in {'failed', 'interrupted', 'completed_with_errors'} or state['partial']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
