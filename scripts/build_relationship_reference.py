"""Create an independent source-table reference for package and bidder facts.

This is a local reference drafted from HTML, not official or double-reviewed
labels. Source cell locations are retained for audit and correction.
"""
from __future__ import annotations

from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT/'data/reference/relationships.jsonl'


def number(text):
    if '%' in text or '折扣' in text or '费率' in text:
        return None
    match = re.search(r'-?\d+(?:\.\d+)?', text.replace(',', ''))
    if not match:
        return None
    return float(Decimal(match.group()) * (10000 if '万' in text else 1))


def package_number(table):
    for node in table.find_all_previous(['p','h2','h3','h4'], limit=25):
        value = node.get_text(' ',strip=True)
        match = re.match(r'\s*(?:合同包|采购包)\s*(\d+)',value)
        if match:
            return str(int(match.group(1)))
    return ''


def main():
    if OUTPUT.exists():
        raise SystemExit('Reference exists; preserve the frozen source audit.')
    reference = [json.loads(line) for line in (ROOT/'data/reference/announcements.jsonl').read_text('utf-8').splitlines()]
    records = []
    for original in reference:
        path = ROOT/original['files'][0]
        soup = BeautifulSoup(path.read_bytes(),'lxml')
        purchaser = ''
        for row in soup.find_all('tr'):
            cells = [cell.get_text(' ',strip=True) for cell in row.find_all(['td','th'],recursive=False)]
            if '采购单位' in cells:
                purchaser = cells[cells.index('采购单位')+1]
                break
        project_name = ''
        for paragraph in soup.find_all(['p','h2','h3','h4']):
            match = re.match(r'二[、.]\s*项目名称\s*[：:]\s*(.+)',paragraph.get_text(' ',strip=True))
            if match:
                project_name = match.group(1)
                break
        packages = {}
        for lot in original['lots']:
            match = re.search(r'(?:合同包|采购包)\s*(\d+)',lot['lot_name'])
            if match:
                packages[str(int(match.group(1)))] = {'lot_name':lot['lot_name'],'awarded_amount':None,'winners':[], 'bids':[]}
        for index, table in enumerate(soup.find_all('table'),1):
            trs = table.find_all('tr')
            if not trs or table.find('table'):
                continue
            headers = [c.get_text(' ',strip=True) for c in trs[0].find_all(['td','th'],recursive=False)]
            package = packages.get(package_number(table))
            if package is None:
                continue
            if '供应商名称' in headers and '中标（成交）金额' in headers:
                for row_number, row in enumerate(trs[1:],2):
                    cells = [c.get_text(' ',strip=True) for c in row.find_all(['td','th'],recursive=False)]
                    if len(cells) < len(headers):
                        continue
                    package['winners'].append(cells[headers.index('供应商名称')])
                    package['awarded_amount'] = number(cells[headers.index('中标（成交）金额')])
            elif all(column in headers for column in ('供应商','资格性审查','符合性审查')):
                for row_number, row in enumerate(trs[1:],2):
                    cells = []
                    for cell in row.find_all(['td','th'],recursive=False):
                        cells.extend([cell.get_text(' ',strip=True)] * int(cell.get('colspan',1)))
                    if len(cells) < 3 or not cells[0]:
                        continue
                    qualification, compliance = cells[1:3]
                    failed = any('不通过' in x or '未通过' in x for x in (qualification, compliance))
                    passed = qualification == compliance == '通过'
                    quote_column = next((headers.index(h) for h in ('最终报价','投标报价','报价') if h in headers),None)
                    bid_amount = number(cells[quote_column]) if quote_column is not None and quote_column < len(cells) else None
                    package['bids'].append({'bidder':cells[0], 'eligible':passed and not failed,
                        'qualification':qualification,'compliance':compliance,'bid_amount':bid_amount,
                        'source_location':f'TABLE:{index} ROW:{row_number}','source_cells':cells})
        for package in packages.values():
            found = {b['bidder'] for b in package['bids']}
            for winner in package['winners']:
                if winner not in found:
                    package['bids'].append({'bidder':winner,'eligible':True,'qualification':'','compliance':'','bid_amount':None,'source_location':'winner-table'})
            for bid in package['bids']:
                bid['is_winner'] = bid['bidder'] in package['winners']
        records.append({'notice_uuid':path.stem,'purchaser':purchaser,'project_name':project_name,
            'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(), 'packages':list(packages.values()),
            'reference_status':'source-table-draft-human-review-pending'})
    OUTPUT.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in records),encoding='utf-8')
    print(json.dumps({'notices':len(records),'packages':sum(len(r['packages']) for r in records),
        'bids':sum(len(p['bids']) for r in records for p in r['packages']),
        'sha256':hashlib.sha256(OUTPUT.read_bytes()).hexdigest()},ensure_ascii=False))


if __name__ == '__main__':
    main()
