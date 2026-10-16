"""Synthetic scale diagnostics on this host, not an official competition benchmark."""
from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import platform
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = ROOT/'.cache'/'benchmark'
SCRATCH.mkdir(parents=True,exist_ok=True)
sys.dont_write_bytecode = True
sys.path.insert(0,str(ROOT/'demo/procurement/backend'))
os.environ['DATABASE_PATH'] = str(SCRATCH/'synthetic-benchmark.db')
os.environ['UPLOAD_DIR'] = str(SCRATCH/'uploads')
os.environ['DEEPSEEK_API_KEY'] = ''
os.environ['MODEL_SETTINGS_PATH'] = str(SCRATCH/'unused-model-settings.local.json')
os.environ['DEMO_SEED'] = 'false'
os.environ['NEO4J_URI'] = ''

from app import analytics
from app.database import connect,init_db,one,upsert_notice
from app.models import BidExtract,ItemExtract,ProjectExtract


def benchmark(size: int,rounds: int) -> dict:
    init_db()
    with connect() as c:
        for table in ('job_documents','jobs','items','bids','projects','notices'):
            c.execute(f'DELETE FROM {table}')
    before = time.perf_counter()
    suppliers = [f'合成供应商{i}' for i in range(10)]
    for index in range(size):
        winner = (index//20)%10
        amount = 1000+index
        record = ProjectExtract(notice_uuid=f'synthetic_{index}',project_name=f'合成项目{index}',purchaser=f'合成采购单位{index%20}',
            lot_name='未分包',awarded_amount=amount,announcement_date='2026-01-01',
            bids=[BidExtract(bidder=name,is_winner=n==winner,bid_amount=amount+n,review_status='通过') for n,name in enumerate(suppliers)],
            items=[ItemExtract(product_name=f'合成产品{n}',brand=f'合成品牌{n}',model=f'M{n}',quantity=1,unit_price=amount/5,total_price=amount/5) for n in range(5)])
        upsert_notice(record,[f'synthetic_{index}.html'],'synthetic')
    population_seconds = time.perf_counter()-before
    operations = {
        'purchaser-partners':lambda:analytics.purchaser_partners('合成采购单位0','synthetic'),
        'purchaser-bidders':lambda:analytics.purchaser_bidders('合成采购单位0','synthetic'),
        'supplier-competitors':lambda:analytics.supplier_competitors(suppliers[0],'synthetic'),
        'common-purchasers':lambda:analytics.common_purchasers(suppliers[:2],'synthetic'),
        'common-projects':lambda:analytics.common_projects(suppliers[:2],'synthetic'),
    }
    results = {}
    for name,operation in operations.items():
        timings = []
        for _ in range(rounds):
            started = time.perf_counter(); data = operation(); timings.append((time.perf_counter()-started)*1000)
        results[name] = {'mean_ms':round(statistics.mean(timings),3),'max_ms':round(max(timings),3),'rounds':rounds,
                         'serialized_bytes':len(json.dumps(data,ensure_ascii=False).encode())}
    assert operations['common-projects']()['summary']['project_count']==size
    return {'checked_at':datetime.now().astimezone().isoformat(),'scope':'本机、合成数据、进程内后端函数；含SQLite读取及聚合，不含网络/浏览器/解析/模型；不能证明官方性能',
            'platform':platform.platform(),'python':platform.python_version(),'cpu_count':os.cpu_count(),
            'limits':'未施加2vCPU/4GB限制','model_calls':0,'database_isolated':True,
            'input':{'notices':size,'packages':size,'bids':size*10,'items':size*5},
            'population_seconds':round(population_seconds,3),'queries':results}


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--notices',type=int,default=1038)
    parser.add_argument('--rounds',type=int,default=5)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    if not 1<=args.notices<=5000 or not 1<=args.rounds<=30:
        parser.error('notice/rounds out of diagnostic range')
    report = benchmark(args.notices,args.rounds)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
