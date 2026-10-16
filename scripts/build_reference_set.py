"""Freeze source-grounded reference rows independently from the model pipeline.

Scope: complete standard eight-column goods tables in selected announcements.
These are programmatically sourced local references, pending independent human
review. Attachment detail and service tables require additional labels.
"""
from __future__ import annotations

from collections import defaultdict
import hashlib
import json
from pathlib import Path
import random
import re

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'data/official-benchmark/html'
OUTPUT = ROOT / 'data/reference'


def amount(text):
    match = re.search(r'\d+(?:\.\d+)?', text.replace(',', ''))
    return float(match.group()) if match else None


def package_label(table):
    for node in table.find_all_previous(['p', 'h1', 'h2', 'h3', 'h4'], limit=25):
        text = node.get_text(' ', strip=True)
        if len(text) > 350:
            continue
        match = re.search(r'(?:合同包|采购包|标包|标段|包)\s*[：:]?\s*[0-9A-Za-z一二三四五六七八九十]+(?:[（(][^（）()]+[)）])?', text)
        if match:
            return match.group().strip()
    return ''


def reference(path):
    raw = path.read_bytes()
    soup = BeautifulSoup(raw, 'lxml')
    lots = defaultdict(list)
    excerpts = []
    for index, table in enumerate(soup.find_all('table'), 1):
        if table.find('table'):
            continue
        trs = table.find_all('tr')
        header = trs[0].get_text(' ', strip=True) if trs else ''
        if not all(word in header for word in ('品目号', '品牌', '数量', '单价', '总价')):
            continue
        label = package_label(table)
        if not label:
            return None
        for row_number, tr in enumerate(trs[1:], 2):
            cells = [cell.get_text(' ', strip=True) for cell in tr.find_all(['td', 'th'], recursive=False)]
            if len(cells) != 8:
                return None
            _, category, product, brand, model, quantity, unit_price, total_price = cells
            item = {'product_name': product, 'category': category, 'brand': brand, 'model': model,
                'quantity': amount(quantity), 'unit_price': amount(unit_price), 'total_price': amount(total_price),
                'source': 'announcement', 'source_file': 'doc-1:' + path.name,
                'line_id': f'TABLE:{index} ROW:{row_number}', 'evidence': ' | '.join(cells)}
            lots[label].append(item)
            excerpts.append({'package': label, 'table': index, 'row': row_number, 'cells': cells})
    total = sum(len(rows) for rows in lots.values())
    if not 1 <= total <= 10:
        return None
    content = soup.select_one('.vF_detail_content')
    if content and '服务类（' in content.get_text(' ', strip=True):
        return None
    return {'notice_uuid': path.stem, 'files': [path.relative_to(ROOT).as_posix()],
        'source_sha256': hashlib.sha256(raw).hexdigest(),
        'reference_scope': 'announcement-standard-goods-tables',
        'review_status': 'algorithmic-draft-pending-source-audit',
        'lots': [{'lot_name': label, 'items': items} for label, items in lots.items()], 'source_rows': excerpts}


def main():
    if (OUTPUT/'announcements.jsonl').exists():
        raise SystemExit('Reference set is frozen; do not overwrite it after viewing model results.')
    candidates = [r for path in sorted(SOURCE.glob('*.html')) if (r := reference(path))]
    rng = random.Random(20261015)
    by_month = defaultdict(list)
    for record in candidates:
        by_month[record['notice_uuid'][1:7]].append(record)
    selected = []
    for month, records in sorted(by_month.items()):
        rng.shuffle(records)
        selected.extend(records[:2])
    rest = [r for r in candidates if r not in selected]
    rng.shuffle(rest)
    selected = (selected + rest)[:20]
    rng.shuffle(selected)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for index, record in enumerate(selected):
        record['split'] = 'diagnostic' if index < 10 else 'holdout'
    target = OUTPUT/'announcements.jsonl'
    target.write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in selected), encoding='utf-8')
    manifest = {'selection_seed': 20261015, 'candidate_notices': len(candidates),
        'reference_status': 'algorithmic-draft-pending-source-audit',
        'scope': '20 source-anchored standard goods-table announcements; excludes attachment/service/scanning validation',
        'sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
        'records': [{'notice_uuid': r['notice_uuid'], 'split': r['split'],
            'items': sum(len(l['items']) for l in r['lots']), 'source_sha256': r['source_sha256']} for r in selected]}
    (OUTPUT/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'references': len(selected), 'items': sum(r['items'] for r in manifest['records']),
        'manifest': 'data/reference/manifest.json', 'sha256': manifest['sha256']}))


if __name__ == '__main__':
    main()
