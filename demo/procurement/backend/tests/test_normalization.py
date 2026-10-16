from app.normalization import money_to_yuan, normalize_org


def test_money_units():
    assert money_to_yuan("12.5万元") == 125000
    assert money_to_yuan("¥1,234.50元") == 1234.5
    assert money_to_yuan("0.2亿元") == 20000000


def test_normalize_org():
    assert normalize_org(" 某 某 科技有限公司：") == "某某科技有限公司"

