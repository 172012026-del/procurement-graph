from app.evidence import ground_evidence
from app.extractor import validate_result
from app.models import ItemExtract, LotExtract, ProjectExtract


def item(file, row, **values):
    return ItemExtract(source_file=file, line_id=row, source_location=row,
        product_name='服务器', model='S1', supplier='供应商甲', quantity=1,
        unit_price=100, total_price=100, business_line_id='1-1', **values)


def test_cross_file_repeats_match_one_to_one_and_preserve_sources():
    result = ProjectExtract(lots=[LotExtract(lot_name='包1', items=[
        item('a.html', 'TABLE:1 ROW:2'), item('a.html', 'TABLE:1 ROW:3'),
        item('b.pdf', 'PAGE:1 LINE:4'), item('b.pdf', 'PAGE:1 LINE:8')])])
    validate_result(result)
    assert len(result.lots[0].items) == 2
    assert all(len(i.related_sources) == 1 for i in result.lots[0].items)
    validate_result(result)  # Database insertion also validates; must be idempotent.
    assert len(result.lots[0].items) == 2


def test_source_code_and_numbers_are_required_and_conflicts_are_preserved():
    first, second = item('a.html', 'TABLE:1 ROW:2'), item('b.pdf', 'PAGE:1 LINE:8')
    second.total_price = 200
    result = ProjectExtract(lots=[LotExtract(lot_name='包1', items=[first, second])])
    validate_result(result)
    assert len(result.lots[0].items) == 2 and result.processing_status == 'partial'
    second.total_price = 100
    second.business_line_id = ''
    validate_result(result)
    assert len(result.lots[0].items) == 2


def test_model_business_code_is_replaced_by_verified_source_row():
    first = item('a.html', 'TABLE:1 ROW:2')
    result = ProjectExtract(lots=[LotExtract(lot_name='包1', items=[first])])
    ground_evidence(result, '[TABLE:1 ROW:2] 2-9 | 服务器 | S1 | 100')
    assert first.business_line_id == '2-9'
    ground_evidence(result, '[TABLE:1 ROW:2] 服务器 | S1 | 100')
    assert first.business_line_id == ''
