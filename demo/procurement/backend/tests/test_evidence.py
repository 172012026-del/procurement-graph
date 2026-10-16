from app.evidence import ground_evidence
from app.extractor import merge_results
from app.models import ItemExtract, LotExtract, ProjectExtract


def test_repeated_source_serial_numbers_do_not_collapse_distinct_goods():
    text = '合同包1(设备采购):\n[TABLE:3 ROW:2] 1-1 | 工作站\n[TABLE:3 ROW:3] 1-1 | 服务器'
    result = ProjectExtract(lots=[LotExtract(lot_name='设备采购', items=[
        ItemExtract(product_name=name, line_id='1-1', source_file='a.html') for name in ('工作站', '服务器')])])
    ground_evidence(result, text)
    merged = merge_results([result])
    assert merged.lots[0].lot_name == '合同包1(设备采购)'
    assert [i.line_id for i in merged.lots[0].items] == ['TABLE:3 ROW:2', 'TABLE:3 ROW:3']


def test_ambiguous_source_identity_is_retained_without_deduplication():
    result = ProjectExtract(lots=[LotExtract(lot_name='包1', items=[
        ItemExtract(product_name='工作站', line_id='1-1', source_file='a.html') for _ in range(2)])])
    ground_evidence(result, '[TABLE:1 ROW:2] 工作站\n[TABLE:1 ROW:3] 工作站')
    assert all(not i.line_id for i in result.lots[0].items)
    assert len(merge_results([result]).lots[0].items) == 2


def test_pdf_split_cells_require_identity_in_one_printed_business_row():
    result = ProjectExtract(lots=[LotExtract(lot_name='包1',items=[
        ItemExtract(product_name='工作站',model='M1',line_id='PAGE:1 LINE:4'),
        ItemExtract(product_name='服务器',model='M2',line_id='PAGE:1 LINE:8')])])
    text='[PAGE:1 LINE:1] 1-1\n[PAGE:1 LINE:2] 工作\n[PAGE:1 LINE:3] 站\n[PAGE:1 LINE:4] M1\n[PAGE:1 LINE:5] 2-1\n[PAGE:1 LINE:6] 服务\n[PAGE:1 LINE:7] 器\n[PAGE:1 LINE:8] M2'
    ground_evidence(result,text)
    assert [i.business_line_id for i in result.lots[0].items]==['1-1','2-1']
