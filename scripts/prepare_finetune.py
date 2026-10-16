"""Prepare notice-level LoRA data; unreviewed predictions remain a draft queue."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'demo/procurement/backend'))


def digest(value) -> str:
    data = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False, sort_keys=True).encode()
    return hashlib.sha256(data).hexdigest()


def prepare(output: Path, reviews: Path | None = None, candidates: Path | None = None):
    from app.models import ProjectExtract
    from app.parsers import parse_file
    from app.prompts import system_prompt, user_prompt
    source = ROOT / 'demo/procurement/data/demo'
    approvals = {row['notice_uuid']:row for row in json.loads(reviews.read_text('utf-8'))} if reviews else {}
    queue, records = [], []
    fields = {'project_name','project_code','purchaser','announcement_date','budget_amount','awarded_amount',
              'lot_name','lots','items','bids','no_target_reason','warnings'}
    for line in (candidates or source / 'sample-results.jsonl').read_text('utf-8').splitlines():
        if not line.strip():
            continue
        result = ProjectExtract.model_validate(json.loads(line))
        uid = result.notice_uuid
        path = source / 'html' / (uid + '.html')
        target = result.model_dump(mode='json', include=fields)
        approval = approvals.get(uid, {})
        identity = {'notice_uuid':uid,'source_sha256':digest(path.read_bytes()),'target_sha256':digest(target)}
        split = 'validation' if int(hashlib.sha256(uid.encode()).hexdigest(),16) % 5 == 0 else 'train'
        approved = approval.get('approved') is True and bool(approval.get('reviewer')) and all(approval.get(key) == value for key,value in identity.items())
        queue.append({**identity,'approved':approved,'reviewer':approval.get('reviewer',''),'split':split})
        records.append({**identity,'split':split,'reviewed':approved,'messages':[
            {'role':'system','content':system_prompt('schema')},
            {'role':'user','content':user_prompt(f'[FILE:doc-1:{path.name} SOURCE:announcement]\n[当前段落]\n' + parse_file(path), [f'doc-1:{path.name}'])},
            {'role':'assistant','content':json.dumps(target,ensure_ascii=False)}]})
    output.mkdir(parents=True,exist_ok=True)
    (output / 'review-queue.json').write_text(json.dumps(queue,ensure_ascii=False,indent=2),encoding='utf-8')
    (output / 'draft.jsonl').write_text(''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in records),encoding='utf-8')
    approved = [row for row in records if row['reviewed']]
    for split in ['train','validation']:
        (output / (split + '.jsonl')).write_text(''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in approved if row['split']==split),encoding='utf-8')
    manifest = {'candidates':len(records),'reviewed':len(approved),
                'train':sum(row['split']=='train' for row in approved),
                'validation':sum(row['split']=='validation' for row in approved),
                'split_unit':'notice_uuid','draft_is_training_data':False,
                'source':'bundled historical predictions; require human source-and-target approval',
                'model_requests':0}
    (output / 'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'results/training')
    parser.add_argument('--reviews', type=Path)
    parser.add_argument('--candidates',type=Path,help='Reviewed/corrected copy of candidate results; preserve the historical sample')
    args = parser.parse_args()
    if not args.output.resolve().is_relative_to(ROOT):
        parser.error('Output must stay inside the repository')
    print(json.dumps(prepare(args.output,args.reviews,args.candidates),ensure_ascii=False))
