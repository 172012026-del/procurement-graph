"""Synthetic source-grounded cases, not an official accuracy benchmark."""
import copy
import io
import json
from pathlib import Path

from openpyxl import load_workbook
import pytest

from app import analytics
from app.database import connect, one, upsert_notice
from app.evidence import ground_evidence
from app.exports import export_records, workbook_bytes
from app.item_hierarchy import analyze_lot, detail_items
from app.models import BidExtract, ItemExtract, LotExtract, ProjectExtract


def grounded_notice():
    parent = ItemExtract(product_name='教学设备',quantity=1,quantity_unit='批',total_price=100,
        supplier='供应商甲',source_file='doc-1:notice.html',line_id='TABLE:1 ROW:2')
    announcement = ProjectExtract(lots=[LotExtract(lot_name='合同包1',items=[parent])])
    ground_evidence(announcement,'合同包1\n[TABLE:1 ROW:2] 1-1 | 教学设备 | 1批 | 总价100元 | '
        '供应商甲 | 本项全部明细详见《报价明细.pdf》')
    children = [ItemExtract(product_name=name,model=model,quantity=1,total_price=amount,
        supplier='供应商甲',source='attachment',source_file='doc-2:报价明细.pdf',line_id=f'PAGE:1 LINE:{index}')
        for index,(name,model,amount) in enumerate([('台式电脑','C1',60),('交换机','S1',40)],1)]
    attachment = ProjectExtract(lots=[LotExtract(lot_name='合同包1',items=children)])
    ground_evidence(attachment,'合同包1\n[PAGE:1 LINE:1] 1-1-1 | 台式电脑 | C1 | 总价60元 | 供应商甲\n'
        '[PAGE:1 LINE:2] 1-1-2 | 交换机 | S1 | 总价40元 | 供应商甲')
    return ProjectExtract(notice_uuid='synthetic-hierarchy',project_name='层级核验样例',purchaser='采购单位甲',
        lots=[LotExtract(lot_name='合同包1',awarded_amount=100,items=[parent,*children],
            bids=[BidExtract(bidder='供应商甲',is_winner=True,bid_amount=100)])])


def relation(result):
    return analyze_lot(result.lots[0])['relations'][0]


def test_confirmed_projection_preserves_source_records_and_disclosed_values():
    result = grounded_notice()
    original = result.model_dump()
    report = analyze_lot(result.lots[0])
    assert report['relations'][0]['status'] == 'confirmed'
    assert report['summary']['source_count'] == 3
    assert report['summary']['detail_count'] == 2
    assert report['summary']['known_amount_source'] == 200
    assert report['summary']['known_amount_detail'] == 100
    assert [item.product_name for item in detail_items(result.lots[0])] == ['台式电脑','交换机']
    assert result.model_dump() == original
    assert analyze_lot(result.lots[0]) == report


@pytest.mark.parametrize('change,failed_check',[
    ('missing_context','grounding'),('tampered_context','grounding'),('supplier_conflict','supplier'),
    ('wrong_package','package'),('missing_total','amounts'),('conflicting_total','amounts'),
    ('duplicate_source_row','rows'),('missing_codes','codes'),('model_total_not_in_source','disclosed_totals'),
    ('missing_package','package'),('nested_summary','flat'),
])
def test_uncertain_or_conflicting_rows_are_never_suppressed(change,failed_check):
    result = grounded_notice()
    lot = result.lots[0]
    parent,first,second = lot.items
    if change == 'missing_context': first.source_context = {}
    elif change == 'tampered_context': first.source_context['text'] += '模型猜测'
    elif change == 'supplier_conflict': first.supplier = '供应商乙'
    elif change == 'wrong_package': first.lot_name = '合同包2'
    elif change == 'missing_total': first.total_price = None
    elif change == 'conflicting_total': first.total_price = 61
    elif change == 'duplicate_source_row': second.source_location = first.source_location
    elif change == 'missing_codes': first.business_line_id = ''
    elif change == 'model_total_not_in_source':
        parent.total_price,first.total_price,second.total_price = 1000,600,400
    elif change == 'missing_package': lot.lot_name = ''
    elif change == 'nested_summary': second.business_line_id = '1-1-1-1'
    report = analyze_lot(lot)
    assert report['relations'][0]['status'] == 'needs_review'
    assert not next(check for check in report['relations'][0]['checks'] if check['code'] == failed_check)['passed']
    assert report['excluded_indices'] == []
    assert len(detail_items(lot)) == 3


@pytest.mark.parametrize('scope',['详见附件','本项部分明细详见《报价明细.pdf》',
    '本项全部明细详见《报价明细.pdf》，仅供参考，不含本项设备'])
def test_amount_agreement_does_not_establish_scope(scope):
    result = grounded_notice()
    parent = result.lots[0].items[0]
    parent.source_context = {}
    ground_evidence(ProjectExtract(lots=[LotExtract(lot_name='合同包1',items=[parent])]),
        '[TABLE:1 ROW:2] 1-1 | 教学设备 | 1批 | 总价100元 | '+scope)
    report = analyze_lot(result.lots[0])
    assert not report['excluded_indices']
    assert all(r['status'] == 'needs_review' for r in report['relations'])


def test_two_parents_and_ambiguous_file_names_remain_unresolved():
    result = grounded_notice()
    lot = result.lots[0]
    lot.items.insert(1,lot.items[0].model_copy(deep=True))
    assert all(r['status'] == 'needs_review' for r in analyze_lot(lot)['relations'])
    result = grounded_notice()
    extra = result.lots[0].items[1].model_copy(deep=True)
    extra.source_file = 'doc-3:报价明细.pdf'
    result.lots[0].items.append(extra)
    assert relation(result)['status'] == 'needs_review'
    assert not next(c for c in relation(result)['checks'] if c['code'] == 'reference')['passed']


def test_grounding_discards_fabricated_context_and_does_not_borrow_nearby_rows():
    result = grounded_notice()
    parent = result.lots[0].items[0]
    ground_evidence(ProjectExtract(lots=[LotExtract(lot_name='合同包1',items=[parent])]),
        '[TABLE:1 ROW:2] 其他设备 | 与当前商品无关')
    assert parent.source_context == {}
    assert not analyze_lot(result.lots[0])['excluded_indices']


@pytest.mark.parametrize('total_text',['总价100元；更正总价200元','总价100e2元'])
def test_ambiguous_or_unsupported_source_amounts_cannot_confirm_a_relation(total_text):
    result = grounded_notice()
    parent = result.lots[0].items[0]
    ground_evidence(ProjectExtract(lots=[LotExtract(lot_name='合同包1',items=[parent])]),
        '[TABLE:1 ROW:2] 1-1 | 教学设备 | 1批 | '+total_text+' | 本项全部明细详见《报价明细.pdf》')
    assert relation(result)['status'] == 'needs_review'


def test_unassigned_rows_in_referenced_document_keep_all_source_rows():
    result = grounded_notice()
    result.lots[0].items.append(ItemExtract(product_name='赠品',total_price=0,
        source='attachment',source_file='doc-2:报价明细.pdf'))
    report = analyze_lot(result.lots[0])
    assert not report['excluded_indices'] and report['summary']['detail_count'] == 4
    assert not next(c for c in report['relations'][0]['checks'] if c['code'] == 'coverage')['passed']


def test_oversized_source_cells_are_not_truncated_into_accepted_evidence():
    result = grounded_notice()
    parent = result.lots[0].items[0]
    ground_evidence(ProjectExtract(lots=[LotExtract(lot_name='合同包1',items=[parent])]),
        '[TABLE:1 ROW:2] 1-1 | 教学设备 | 1批 | 总价100元 | 本项全部明细详见《报价明细.pdf》'+('说明'*9000))
    assert not parent.source_context and not analyze_lot(result.lots[0])['excluded_indices']


def cells(content):
    workbook = load_workbook(io.BytesIO(content),read_only=True,data_only=False)
    try:
        return {sheet.title:list(sheet.values) for sheet in workbook}
    finally:
        workbook.close()


def test_opt_in_export_changes_only_item_rows_and_retains_three_sheet_schema():
    result = grounded_notice()
    source = cells(workbook_bytes([result]))
    detail = cells(workbook_bytes([result],item_view='detail'))
    assert list(detail) == ['总表','标的表','投标人表']
    assert source['总表'] == detail['总表']
    assert source['投标人表'] == detail['投标人表']
    assert source['标的表'][0] == detail['标的表'][0]
    assert len(source['标的表']) == 4 and len(detail['标的表']) == 3
    assert [row[3] for row in detail['标的表'][1:]] == ['台式电脑','交换机']
    assert [row[9] for row in detail['标的表'][1:]] == [.006,.004]
    with pytest.raises(ValueError): workbook_bytes([result],item_view='unknown')


def test_api_snapshot_batch_export_and_relationships_remain_compatible(client):
    result = grounded_notice()
    project = upsert_notice(result,['notice.html','报价明细.pdf'],'hierarchy')[0]
    before = analytics.purchaser_partners('采购单位甲','hierarchy')
    response = client.get(f'/api/projects/{project}',params={'dataset_id':'hierarchy'})
    assert response.status_code == 200
    assert len(response.json()['items']) == 3
    assert response.json()['item_hierarchy']['summary']['confirmed_groups'] == 1
    assert client.get(f'/api/projects/{project}',params={'dataset_id':'other'}).status_code == 404
    for view,count in [('source',4),('detail',3)]:
        response = client.get('/api/export/standard.xlsx',params={'dataset_id':'hierarchy','item_view':view})
        assert response.status_code == 200 and len(cells(response.content)['标的表']) == count
    assert client.get('/api/export/standard.xlsx?item_view=unknown').status_code == 422
    audit = client.get('/api/export/quality.json?dataset_id=hierarchy&item_view=detail').json()
    assert audit['item_view'] == 'detail'
    assert audit['notices'][0]['item_hierarchy'][0]['summary']['detail_count'] == 2
    assert analytics.purchaser_partners('采购单位甲','hierarchy') == before
    records,_ = export_records('hierarchy')
    assert len(records[0].lots[0].items) == 3
    with connect() as connection:
        connection.execute('INSERT INTO jobs(id,dataset_id,status,mode) VALUES(?,?,?,?)',
            ('hierarchy-batch','hierarchy','completed','replay'))
        stored = one('SELECT result_json FROM notices WHERE dataset_id=?',('hierarchy',))
        connection.execute('INSERT INTO job_documents(job_id,notice_uuid,status,result_json) VALUES(?,?,?,?)',
            ('hierarchy-batch',result.notice_uuid,'complete',stored['result_json']))
    response = client.get('/api/export/standard.xlsx?dataset_id=hierarchy&job_id=hierarchy-batch&item_view=detail')
    assert response.status_code == 200 and len(cells(response.content)['标的表']) == 3


def test_changed_database_row_cannot_reuse_stale_snapshot_context(client):
    project = upsert_notice(grounded_notice(),['notice.html'],'hierarchy')[0]
    with connect() as connection:
        connection.execute('UPDATE items SET total_price=999 WHERE project_id=? AND product_name=?',(project,'台式电脑'))
    report = client.get(f'/api/projects/{project}?dataset_id=hierarchy').json()['item_hierarchy']
    assert report['summary']['confirmed_groups'] == 0 and not report['excluded_indices']


def test_malformed_legacy_snapshot_or_metadata_does_not_break_project_details(client):
    project = upsert_notice(grounded_notice(),['notice.html'],'hierarchy')[0]
    with connect() as connection:
        connection.execute("UPDATE notices SET result_json='{broken' WHERE dataset_id='hierarchy'")
        connection.execute("UPDATE items SET related_sources='{broken',derived_values='[]' WHERE project_id=?",(project,))
    response = client.get(f'/api/projects/{project}?dataset_id=hierarchy')
    assert response.status_code == 200 and len(response.json()['items']) == 3
    assert response.json()['item_hierarchy']['excluded_indices'] == []


def test_all_bundled_historical_rows_and_workbook_cells_are_preserved():
    root = Path(__file__).resolve().parents[2]
    records = [ProjectExtract.model_validate_json(line) for line in
        (root/'data/demo/sample-results.jsonl').read_text('utf-8-sig').splitlines() if line.strip()]
    before = copy.deepcopy([record.model_dump() for record in records])
    source = cells(workbook_bytes(records))
    detail = cells(workbook_bytes(records,item_view='detail'))
    assert len(records) == 20 and len(source['总表'])-1 == 26
    assert len(source['标的表'])-1 == 138
    assert source == detail
    assert [record.model_dump() for record in records] == before
