import pytest
import pandas as pd
import io

@pytest.fixture
def sample_df():
    data = [
        {"name": "焼鳥 鳥一郎", "address": "東京都新宿区歌舞伎町1-2-3", "phone": "03-1234-5678", "source": "google"},
        {"name": "鳥一郎 新宿店", "address": "新宿区歌舞伎町1丁目2番3号", "phone": "0312345678", "source": "tabelog"},
        {"name": "居酒屋 太郎", "address": "東京都渋谷区道玄坂2-2-2", "phone": "03-9999-9999", "source": "google"},
        {"name": "Sushi Sato", "address": "Tokyo Chuo-ku Ginza 1-1-1", "phone": "03-1111-2222", "source": "hotpepper"},
    ]
    return pd.DataFrame(data)

@pytest.fixture
def csv_file_factory():
    def _create_csv(data_list):
        df = pd.DataFrame(data_list)
        buf = io.StringIO()
        df.to_csv(buf, index=False, encoding="utf-8-sig")
        return buf.getvalue()
    return _create_csv
