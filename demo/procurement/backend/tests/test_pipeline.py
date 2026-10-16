import asyncio
from pathlib import Path

from app.extractor import DeepSeekExtractor
from app.parsers import parse_file


FIXTURE = Path(__file__).parent / "fixtures/sample.html"


def test_html_parser_keeps_table_rows():
    text = parse_file(FIXTURE)
    assert "采购标的 | 品牌 | 规格型号 | 数量 | 总价" in text
    assert "核心交换机 | 示例品牌 | S9000 | 2 | 1080000元" in text


def test_offline_fallback_extracts_project_fields():
    result = asyncio.run(DeepSeekExtractor().extract([FIXTURE]))
    assert result.project_code == "TEST-2026-001"
    assert result.purchaser == "示例大学"
    assert result.budget_amount == 1_200_000
    assert result.awarded_amount == 1_080_000
    assert result.bids[0].bidder == "示例科技有限公司"
    assert result.extraction_method == "heuristic-fallback"

