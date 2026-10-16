"""Package a disclosed public sample and its historical responses, without keys."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import re
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    source = ROOT/'results/offline-release'
    target = ROOT/'demo/procurement/data/demo'
    if not (source/'run-report.json').is_file():
        manifest=json.loads((target/'manifest.json').read_text('utf-8'))
        for name,digest in manifest['source_files_sha256'].items():
            if hashlib.sha256((target/'html'/name).read_bytes()).hexdigest()!=digest:
                raise ValueError('Bundled source checksum mismatch: '+name)
        if not all((target/'cache'/name).is_file() for name in manifest['response_cache_files']):
            raise ValueError('Bundled historical responses are incomplete')
        if not (target/'sample-results.jsonl').is_file() or not (target/'sample-announcements.zip').is_file():
            raise ValueError('Bundled sample results or input ZIP is missing')
        print(json.dumps({'mode':'bundled-validation','notices':manifest['notices'],'model_requests':0}))
        return
    report = json.loads((source/'run-report.json').read_text('utf-8'))
    if report['job']['metrics']['model_calls'] != 0:
        raise ValueError('The release evidence must use offline replay')
    (target/'html').mkdir(parents=True,exist_ok=True)
    (target/'cache').mkdir(parents=True,exist_ok=True)
    results = [json.loads(line) for line in (source/'predictions.jsonl').read_text('utf-8').splitlines() if line.strip()]
    ids = [r['notice_uuid'] for r in results]
    files = {}
    with zipfile.ZipFile(target/'sample-announcements.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for uid in ids:
            if not re.fullmatch(r't\d{8}_\d+',uid):
                raise ValueError('Invalid public sample ID')
            path = ROOT/'data/official-benchmark/html'/(uid+'.html')
            if not path.is_file():
                path=target/'html'/(uid+'.html')
            if path.resolve() != (target/'html'/path.name).resolve():
                shutil.copyfile(path,target/'html'/path.name)
            archive.write(path,path.name)
            files[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    keys = report['job']['metrics']['response_cache_keys']
    for key in keys:
        if not re.fullmatch(r'[a-f0-9]{64}\.json', key):
            raise ValueError('Invalid response cache key')
        path = ROOT/'.cache/model-responses'/key
        if not path.is_file():
            path = target/'cache'/key
        if not path.is_file():
            raise FileNotFoundError('Historical response unavailable: ' + key)
        envelope = json.loads(path.read_text('utf-8'))
        # Only the service response is packaged. No request headers/configuration.
        allowed = {k:v for k,v in envelope.items() if k in {'id','object','created','model','choices','usage','system_fingerprint'}}
        (target/'cache'/key).write_text(json.dumps(allowed,ensure_ascii=False),encoding='utf-8')
    shutil.copyfile(source/'predictions.jsonl',target/'sample-results.jsonl')
    manifest = {'available':True,'notice_ids':ids,'notices':len(ids),'packages':report['results']['packages'],
        'items':report['results']['items'],'bids':report['results']['bids'],
        'scope':'announcement-only historical model response replay',
        'reference_rows':79,'reference_status':'programmatic-source-check; human review pending; not official gold',
        'source_files_sha256':files,'response_cache_files':keys,
        'network_policy':'cache-only; missing response fails without a model request'}
    (target/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:manifest[k] for k in ('notices','packages','items','bids')},ensure_ascii=False))


if __name__=='__main__':
    main()
