from app.normalization import model_match_key, money_to_yuan, normalize_org


def test_money_units():
    assert money_to_yuan("12.5万元") == 125000
    assert money_to_yuan("¥1,234.50元") == 1234.5
    assert money_to_yuan("0.2亿元") == 20000000


def test_normalize_org():
    assert normalize_org(" 某 某 科技有限公司：") == "某某科技有限公司"


def test_model_match_key_drops_only_whitespace():
    assert model_match_key("DH-ITSE0400-TA -N02") == "DH-ITSE0400-TA-N02"
    assert model_match_key(" DH-ITSE0400-TA\n-N02 ") == model_match_key("DH-ITSE0400-TA-N02")
    assert model_match_key("DH-ITSE0400-TA\u3000-N02") == "DH-ITSE0400-TA-N02"
    assert model_match_key("Model A") != model_match_key("model a")
    assert model_match_key("DS-7816N-Q2/16P(B）") == "DS-7816N-Q2/16P(B）"
    assert model_match_key("250m³/d") == "250m³/d"

