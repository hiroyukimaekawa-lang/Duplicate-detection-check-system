import pytest
from .normalizer import normalize_name, normalize_address, extract_municipality

def test_normalize_name():
    # Corporate suffixes
    assert normalize_name("株式会社 焼鳥鳥一郎") == "焼鳥鳥一郎"
    assert normalize_name("焼鳥鳥一郎（株）") == "焼鳥鳥一郎"
    assert normalize_name("㈱焼鳥鳥一郎") == "焼鳥鳥一郎"
    assert normalize_name("有限会社 鳥二郎") == "鳥二郎"
    assert normalize_name("LLC Restaurant") == "restaurant"
    
    # Decoration symbols
    assert normalize_name("焼鳥★鳥一郎") == "焼鳥 鳥一郎"
    assert normalize_name("【新宿店】焼鳥鳥一郎") == "新宿店 焼鳥鳥一郎"
    assert normalize_name("♪メロディカフェ") == "メロディカフェ"
    assert normalize_name("◇和食処◇") == "和食処"
    
    # "The", "ザ・" removal
    assert normalize_name("ザ・コーヒーショップ") == "コーヒーショップ"
    assert normalize_name("ザ コーヒーショップ") == "コーヒーショップ"
    assert normalize_name("The Coffee Shop") == "coffee shop"
    assert normalize_name("ザ・居酒屋") == "居酒屋"
    
    # Case unification and spaces
    assert normalize_name("  ROBOT  CAFE  ") == "robot cafe"
    assert normalize_name("焼鳥  鳥一郎") == "焼鳥 鳥一郎"
    
    # Special characters
    assert normalize_name("居酒屋・太郎") == "居酒屋・太郎" # Keep middle dot if possible or space

def test_normalize_address():
    # Prefecture unification
    assert normalize_address("東京新宿区...") == "東京都新宿区"
    assert normalize_address("大阪北区...") == "大阪府北区"
    
    # Kanji numbers and block/lot
    assert normalize_address("東京都新宿区歌舞伎町一丁目2番地3号") == "東京都新宿区歌舞伎町1-2-3"
    assert normalize_address("東京都新宿区歌舞伎町3-4-5") == "東京都新宿区歌舞伎町3-4-5"
    assert normalize_address("東京都中央区銀座三丁目4-5") == "東京都中央区銀座3-4-5"
    
    # Building and floor removal
    assert normalize_address("東京都新宿区歌舞伎町1-2-3 新宿ビル3F") == "東京都新宿区歌舞伎町1-2-3"
    assert normalize_address("東京都港区六本木6-10-1 六本木ヒルズ 森タワー 49階") == "東京都港区六本木6-10-1"
    assert normalize_address("東京都中央区銀座1-1-1 某ビルB1F") == "東京都中央区銀座1-1-1"
    
    # Symbol normalization
    assert normalize_address("東京都新宿区歌舞伎町１－２－３") == "東京都新宿区歌舞伎町1-2-3"
    assert normalize_address("東京都新宿区歌舞伎町1―2―3") == "東京都新宿区歌舞伎町1-2-3"

def test_extract_municipality():
    assert extract_municipality("東京都新宿区歌舞伎町1-2-3") == ("東京都", "新宿区")
    assert extract_municipality("大阪府大阪市北区梅田1-1-1") == ("大阪府", "大阪市北区")
    assert extract_municipality("神奈川県横浜市中区山下町") == ("神奈川県", "横浜市中区")
    assert extract_municipality("北海道札幌市中央区") == ("北海道", "札幌市中央区")
    assert extract_municipality("千葉県船橋市本町") == ("千葉県", "船橋市")

if __name__ == "__main__":
    pytest.main([__file__])
