from __future__ import annotations

import json
from .config import ROOT
from .database import insert_project, one, upsert_notice
from .models import BidExtract, ItemExtract, ProjectExtract


def seed_reference() -> None:
    """Install the disclosed historical sample once; never overwrite user data."""
    path = ROOT/'data/demo/sample-results.jsonl'
    if not path.is_file() or one("SELECT COUNT(*) count FROM notices WHERE dataset_id='official-reference'").get('count', 0):
        return
    for line in path.read_text('utf-8').splitlines():
        if line.strip():
            result = ProjectExtract.model_validate(json.loads(line))
            upsert_notice(result, [result.notice_uuid+'.html'], 'official-reference')


PROJECTS = [
    ("智慧医院数据中心扩容项目", "广州市增城区中心医院", 2380000, "联通数智医疗科技有限公司", [("中国电信股份有限公司广东分公司", 2310000), ("广州云奕技术有限公司", 2450000)], "浪潮服务器", "浪潮", "NF5280M6"),
    ("政务云安全服务采购", "广州市政务服务和数据管理局", 1680000, "中国电信股份有限公司广东分公司", [("联通数智医疗科技有限公司", 1720000), ("广东数字科技有限公司", 1790000)], "云安全服务", "天翼云", "高级版"),
    ("基层医疗信息化升级", "广州市增城区中心医院", 1260000, "联通数智医疗科技有限公司", [("广州云奕技术有限公司", 1300000), ("广东数字科技有限公司", 1330000)], "医院信息平台", "联通数科", "V3.2"),
    ("教育专网升级改造", "广州市教育局", 3150000, "广州云奕技术有限公司", [("中国电信股份有限公司广东分公司", 3200000), ("联通数智医疗科技有限公司", 3270000)], "核心交换机", "新华三", "S12508X"),
    ("公共数据运营平台", "广州市政务服务和数据管理局", 4280000, "联通数智医疗科技有限公司", [("中国电信股份有限公司广东分公司", 4350000), ("广州云奕技术有限公司", 4490000)], "数据治理平台", "联通数科", "V2.0"),
    ("区域影像云建设", "广州市增城区中心医院", 3560000, "中国电信股份有限公司广东分公司", [("联通数智医疗科技有限公司", 3610000), ("广东数字科技有限公司", 3720000)], "影像云服务", "天翼云", "医疗版"),
]


def seed_demo() -> None:
    if one("SELECT COUNT(*) AS count FROM projects WHERE dataset_id='demo'").get("count", 0):
        return
    for index, (name, purchaser, amount, winner, losers, product, brand, model) in enumerate(PROJECTS, 1):
        bids = [BidExtract(bidder=winner, is_winner=True, bid_amount=amount, score=95 - index / 10, rank=1)]
        bids.extend(BidExtract(bidder=bidder, is_winner=False, bid_amount=price, score=90 - pos, rank=pos + 2,review_status='通过') for pos, (bidder, price) in enumerate(losers))
        insert_project(
            ProjectExtract(
                notice_uuid=f'demo_{index}',lot_name='未分包',
                project_name=name,
                project_code=f"DEMO-2026-{index:03d}",
                purchaser=purchaser,
                budget_amount=round(amount * 1.08, 2),
                awarded_amount=amount,
                announcement_date=f"2026-0{(index + 1) // 2}-{10 + index:02d}",
                bids=bids,
                items=[ItemExtract(product_name=product, category="信息化设备或服务", brand=brand, model=model, unit_price=amount, quantity=1, total_price=amount, supplier=winner, confidence=0.98, evidence="脱敏演示数据")],
                extraction_method="demo-seed",
            ),
            [f"demo_{index}.html"],
            dataset_id='demo',
        )
