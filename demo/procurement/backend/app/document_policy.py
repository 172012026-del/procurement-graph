"""Identify supporting documents that do not establish a transaction line.

All files are still parsed and retained in the audit/cache. Supplier policy
declarations and blank tender templates are not additional awarded items or a
bidder/award list. Unclassified attachments remain eligible for model extraction.
"""
from __future__ import annotations

import re
import unicodedata


def document_role(filename: str, text: str) -> tuple[str, str]:
    name = re.sub(r'\s+', '', unicodedata.normalize('NFKC', filename))
    declaration = any(word in name for word in ('中小企业声明', '本国产品声明', '残疾人福利', '监狱企业', '政策适用性说明')) or bool(re.search(r'本国产品.{0,30}声明', name))
    # A combined attachment can contain a declaration and a real quote. Keep it
    # eligible when its text contains both a quote heading and price columns.
    compact = re.sub(r'\s+', '', text)
    mixed_quote = bool(re.search(r'分项报价表|报价明细表|报价明细附件', compact) and re.search(r'单价.{0,120}(?:金额|总价|合计|小计)', compact))
    if declaration and mixed_quote:
        return 'mixed-transaction-evidence', ''
    if declaration:
        return 'supporting-declaration', '政策资格声明不作为新增成交标的或中标、报价事实；保留原文解析供复核'
    if any(word in name for word in ('分项报价','报价明细','明细附件','成交明细','中标明细','评审','得分','未中标','中标结果','成交结果')):
        return 'transaction-evidence', ''
    if any(word in name for word in ('招标文件','采购文件','磋商文件','谈判文件','询价文件','征求意见稿','采购需求','投标须知')):
        return 'requirements-template', '采购需求和招标模板不证明已成交商品、实际投标报价或审查结果；保留原文解析供复核'
    heading = re.sub(r'\s+', '', text[:1800])
    if ('招标文件' in heading or '竞争性磋商文件' in heading) and re.search(r'投标人须知|供应商须知|第一章|目录', heading):
        return 'requirements-template', '文档首页明确为招标/磋商文件；不把需求或空白模板写入成交事实'
    return 'unclassified-attachment', ''
