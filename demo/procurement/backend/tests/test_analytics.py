import pytest
from app import analytics
from app.database import insert_project,upsert_notice
from app.models import BidExtract,ItemExtract,LotExtract,ProjectExtract

@pytest.fixture(autouse=True)
def example_notices():
    for index,winner in enumerate(('供应商甲','供应商乙'),1):
        insert_project(ProjectExtract(project_name=f'项目{index}',purchaser='采购单位A',lot_name='未分包',awarded_amount=100*index,
            bids=[BidExtract(bidder=winner,is_winner=True,bid_amount=100*index),
                  BidExtract(bidder='供应商丙',bid_amount=120*index,review_status='通过'),
                  BidExtract(bidder='供应商甲' if winner=='供应商乙' else '供应商乙',bid_amount=130*index,review_status='通过')],
            items=[ItemExtract(product_name='服务器',brand='品牌X',total_price=100*index,supplier=winner)]),[f'p{index}.html'])

def test_purchaser_partners():
    result=analytics.purchaser_partners('采购单位A')
    assert len(result['winning_suppliers'])==2
    assert sum(r['cooperation_count'] for r in result['winning_suppliers'])==2
    assert result['product_suppliers'][0]['cooperation_count']==2

def test_purchaser_bidders_and_pairs():
    result=analytics.purchaser_bidders('采购单位A')
    assert result['top_bidders'][0]['frequency']==2
    assert any(p['frequency']==2 for p in result['collaborative_pairs'])

def test_supplier_competitors():
    result=analytics.supplier_competitors('供应商甲')
    assert {r['bidder'] for r in result['all_participants']} >= {'供应商乙','供应商丙'}

def test_common_queries():
    result=analytics.common_purchasers(['供应商甲','供应商乙'])
    assert result['purchasers'][0]['purchaser']=='采购单位A'
    assert result['purchasers'][0]['total_amount']==300
    assert analytics.common_projects(['供应商甲','供应商乙'])['summary']['project_count']==2
