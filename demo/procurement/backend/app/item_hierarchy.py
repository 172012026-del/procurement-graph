"""Evidence-gated summary/detail views; source records are never deleted.

The initial rule supports explicit cross-file references and printed descendant
business codes. Ambiguous scope, conflicting totals and missing context keep
every row. A matching amount alone is never a relationship signal.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
import hashlib
import ntpath
import re
import unicodedata

from .models import ItemExtract, LotExtract
from .normalization import dedupe_key, lot_identity, normalize_org
from .normalization import money_to_yuan

VERSION = 'item-hierarchy-v1'
POLICY = '原文记录完整保留；明细视图仅折叠证据与范围均通过核验的摘要；金额一致不能单独证明包含关系'
_LOCATION = re.compile(r'\[?(?:(?:TABLE:\s*\d+\s+ROW:\s*\d+|SHEET:[^\]\n]+?\s+ROW:\s*\d+)(?:\s+ITEM:\s*\d+)?|(?:PAGE|IMAGE):\s*\d+\s+LINE:\s*\d+)\]?', re.I)
_SCOPE = re.compile(r'(?:本项|该项|本品目|该品目).{0,6}(?:全部|完整).{0,8}(?:明细|清单|设备|货物|产品|内容)')
_NEGATION = re.compile(r'不含|不包含|不包括|未包含|不属于|非本项|不适用|仅供参考|另计|已作废|废止|无效')


def make_context(source_file: str, location: str, text: str) -> dict[str, str]:
    """Called only by the source-grounding step, using the actual parsed row."""
    if len(text) > 16384:
        return {}  # An oversized cell is not silently truncated into proof.
    payload = '\n'.join([source_file, location, text])
    return {'source_file': source_file, 'location': location, 'text': text,
            'sha256': hashlib.sha256(payload.encode()).hexdigest()}


def _verified(item: ItemExtract) -> bool:
    context = item.source_context
    text = context.get('text', '')
    if not text or not item.source_file or not item.line_id or not item.source_location:
        return False
    if context != make_context(item.source_file, item.source_location, text):
        return False
    if not _LOCATION.fullmatch(item.line_id) or not item.product_name:
        return False
    if dedupe_key(item.product_name) not in dedupe_key(text):
        return False
    if item.model and dedupe_key(item.model) not in dedupe_key(text):
        return False
    # An identifier returned by a model does not prove a printed hierarchy.
    body = _LOCATION.sub('', text).strip()
    code = re.match(r'^(\d+(?:-\d+)+)(?=\s|\||$)', body)
    return bool(code and code.group(1) == item.business_line_id)


def _compact(value: str) -> str:
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', value)).casefold()


def _basename(value: str) -> str:
    return ntpath.basename(re.sub(r'^doc-\d+:', '', value))


def _amount(value) -> Decimal | None:
    try:
        number = Decimal(str(value))
        return number if number.is_finite() and number >= 0 else None
    except InvalidOperation:
        return None


def _known_amount(items) -> float | None:
    values = [_amount(item.total_price) for item in items]
    known = [value for value in values if value is not None]
    return float(sum(known, Decimal(0))) if known else None


def _disclosed_total(item: ItemExtract) -> bool:
    text = item.source_context.get('text', '')
    matches = re.findall(r'(?:总价|合计金额|金额合计|小计|总金额)\s*[：:|]?\s*[¥￥]?\s*'
                         r'([0-9][0-9,，]*(?:\.\d+)?\s*(?:万元|元)?)(?=$|[\s|，。；;、（）()\]])', text)
    amount = _amount(item.total_price)
    values = {_amount(money_to_yuan(value)) for value in matches}
    return amount is not None and values == {amount}


def analyze_lot(lot: LotExtract) -> dict:
    """Return a deterministic, non-mutating projection of a single package."""
    items = lot.items
    keys = [f'row-{index + 1}' for index in range(len(items))]
    files = defaultdict(list)
    for index, item in enumerate(items):
        if item.source_file:
            files[item.source_file].append(index)
    relations = []
    for parent_index, parent in enumerate(items):
        if parent.quantity != 1 or parent.quantity_unit not in {'批', '套', '项', '包', '组'}:
            continue
        text = parent.source_context.get('text') or parent.evidence
        referenced = [name for name in files if name != parent.source_file
                      and len(_basename(name)) > 4 and _compact(_basename(name)) in _compact(text)]
        if not referenced:
            continue
        prefix = parent.business_line_id + '-'
        all_rows = [index for name in referenced for index in files[name]]
        children = [index for index in all_rows if parent.business_line_id
                    and items[index].business_line_id.startswith(prefix)]
        if not children:
            children = all_rows
        checks = []

        def check(code, passed, description):
            checks.append({'code': code, 'passed': bool(passed), 'description': description})

        check('package', bool(lot.lot_name) and all(not items[i].lot_name or
              lot_identity(items[i].lot_name) == lot_identity(lot.lot_name) for i in [parent_index, *children]),
              '摘要与明细属于同一个已识别采购包')
        check('reference', len(referenced) == 1, '原文明确引用唯一来源文件')
        check('scope', bool(_SCOPE.search(text)) and not _NEGATION.search(text),
              '原文明确说明本项全部明细的范围，且无否定、另计或作废说明')
        check('grounding', _verified(parent) and all(_verified(items[i]) for i in children),
              '摘要和每条明细均有程序从输入中定位并校验的原文行')
        check('summary_measure', bool(re.search(r'(?<![\d.])1(?:\.0+)?\s*(?:\|\s*)?' +
              re.escape(parent.quantity_unit) + r'(?=\s|\||$|[，。；])', text)),
              '原文明确披露摘要以一批、一套或一个整体项目计量')
        check('codes', bool(parent.business_line_id) and len(children) >= 2 and
              all(items[i].business_line_id.startswith(prefix) for i in children),
              '至少两条明细的原文业务编号是摘要编号的下级')
        check('coverage', all(items[i].business_line_id for i in all_rows),
              '引用文件在本包内没有业务编号缺失、无法判断是否属于本项的记录')
        supplier = normalize_org(parent.supplier)
        check('supplier', bool(supplier) and all(normalize_org(items[i].supplier) == supplier for i in children),
              '摘要与所有明细的已披露供应商一致')
        check('disclosed_totals', _disclosed_total(parent) and all(_disclosed_total(items[i]) for i in children),
              '每个总价均能在对应原文片段的总价或小计字段找到，未采用模型补算值')
        anchors = [(items[i].source_file, items[i].source_location) for i in children]
        check('rows', len(anchors) == len(set(anchors)) and all(location for _, location in anchors),
              '每条明细拥有不同的原文定位，未把重复提取当作多条明细')
        codes = [items[i].business_line_id for i in children]
        check('flat', not any(a != b and b.startswith(a + '-') for a in codes for b in codes),
              '本组明细没有混入尚未处理的多层摘要')
        amounts = [_amount(items[i].total_price) for i in children]
        parent_amount = _amount(parent.total_price)
        amount_ok = parent_amount is not None and parent_amount > 0 and all(a is not None for a in amounts)
        check('amounts', amount_ok and abs(parent_amount - sum((a for a in amounts if a is not None), Decimal(0))) <= Decimal('.01'),
              '原文披露的明细总价之和与摘要总价一致（只检查，不补算缺失字段）')
        relations.append({'parent': keys[parent_index], 'children': [keys[i] for i in children],
                          'parent_index': parent_index, 'child_indices': children,
                          'source_files': referenced, 'checks': checks})
    owners = Counter(child for relation in relations for child in relation['children'])
    for relation in relations:
        relation['checks'].append({'code': 'unique_parent',
            'passed': all(owners[key] == 1 for key in relation['children']),
            'description': '明细没有同时被多个摘要声明包含'})
        relation['status'] = 'confirmed' if all(check['passed'] for check in relation['checks']) else 'needs_review'
        relation['reasons'] = [check['description'] for check in relation['checks'] if not check['passed']]
    excluded = {relation['parent_index'] for relation in relations if relation['status'] == 'confirmed'}
    roles = {}
    for relation in relations:
        if relation['status'] == 'confirmed':
            roles[relation['parent']] = 'summary'
            roles.update((key, 'detail') for key in relation['children'])
    selected = [item for index, item in enumerate(items) if index not in excluded]
    return {'version': VERSION, 'policy': POLICY, 'lot_name': lot.lot_name,
            'summary': {'source_count': len(items), 'detail_count': len(selected),
                        'confirmed_groups': sum(r['status'] == 'confirmed' for r in relations),
                        'review_groups': sum(r['status'] == 'needs_review' for r in relations),
                        'excluded_summary_count': len(excluded),
                        'known_amount_source': _known_amount(items), 'known_amount_detail': _known_amount(selected),
                        'unknown_amount_count': sum(_amount(item.total_price) is None for item in selected)},
            'excluded_indices': sorted(excluded), 'relations': relations,
            'nodes': [{'key': keys[index], 'index': index, 'role': roles.get(keys[index], 'source'),
                       'included_in_detail': index not in excluded, 'item': item.model_dump()}
                      for index, item in enumerate(items)]}


def detail_items(lot: LotExtract) -> list[ItemExtract]:
    excluded = set(analyze_lot(lot)['excluded_indices'])
    return [item for index, item in enumerate(lot.items) if index not in excluded]
