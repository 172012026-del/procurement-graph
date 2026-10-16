from app.document_policy import document_role
from app.evidence import align_attachment_packages
from app.models import ItemExtract, LotExtract, ProjectExtract


def test_tender_templates_and_policy_declarations_are_not_awards():
    assert document_role('招标文件.pdf','')[1]
    assert document_role('合同包1：中小企业声明函.pdf','')[1]
    assert not document_role('合同包1：报价明细附件.pdf','')[1]
    assert not document_role('得分及审查结果.docx','')[1]
    assert not document_role('扫描附件.pdf','')[1]
    assert document_role('关于符合本国产品标准的声明函等有关证明文件.pdf', '')[1]
    assert document_role('本国产品《声明函》.pdf', '')[1]
    assert not document_role('本国产品声明及分项报价.pdf', '分项报价表 品名 单价 数量 小计')[1]


def test_attachment_references_match_explicit_source_package_without_broadcast():
    announcement = ProjectExtract(lots=[LotExtract(lot_name='合同包1(设备采购)'),LotExtract(lot_name='合同包2(软件采购)')])
    result = ProjectExtract(lots=[LotExtract(items=[ItemExtract(product_name='服务器')])])
    align_attachment_packages(result,announcement,'合同包1：报价明细附件.pdf','')
    assert result.lots[0].lot_name == '合同包1(设备采购)'
    unknown = ProjectExtract(lots=[LotExtract(items=[ItemExtract(product_name='服务器')])])
    align_attachment_packages(unknown,announcement,'报价明细.pdf','')
    assert unknown.lots[0].lot_name == ''


def test_captcha_download_response_is_not_a_parse_success(tmp_path):
    import pytest
    from app.parsers import ParseError, parse_file
    source = tmp_path/'document.doc'
    source.write_text('<html><table><tr><td>请输入验证码：再次下载请刷新页面</td></tr></table></html>',encoding='utf-8')
    with pytest.raises(ParseError,match='验证页面'):
        parse_file(source)
