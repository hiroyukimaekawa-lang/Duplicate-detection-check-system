import pytest
import pandas as pd
from ..dedup_engine import run_dedup, is_duplicate, preprocess

def test_preprocess_logic():
    df = pd.DataFrame([
        {"name": "株式会社 焼鳥鳥一郎", "address": "東京都新宿区歌舞伎町一丁目2番地3号", "phone": "03-1234-5678", "source": "google"}
    ])
    processed = preprocess(df)
    
    assert processed.iloc[0]["_norm_name"] == "焼鳥鳥一郎"
    assert processed.iloc[0]["_norm_address"] == "東京都新宿区歌舞伎町1-2-3"
    assert processed.iloc[0]["_municipality"] == "東京都新宿区"
    assert processed.iloc[0]["_norm_phone"] == "0312345678"

def test_is_duplicate_logic():
    # Setup two similar rows
    df = pd.DataFrame([
        {"name": "焼鳥 鳥一郎", "address": "東京都新宿区歌舞伎町1-2-3", "phone": "03-1234-5678", "source": "google"},
        {"name": "鳥一郎 新宿店", "address": "新宿区歌舞伎町1丁目2番3号", "phone": "0312345678", "source": "tabelog"}
    ])
    df = preprocess(df)
    
    # These should be duplicates based on phone
    is_dup, reason, score = is_duplicate(df, 0, 1)
    assert is_dup is True
    assert "phone" in reason

def test_run_dedup_flow(sample_df):
    cleaned, duplicates, stats = run_dedup(sample_df)
    
    # Sample_df has 4 rows, row 0 and 1 are duplicates
    assert len(cleaned) == 3
    assert len(duplicates) == 1
    assert stats["dup_count"] == 1
    assert duplicates.iloc[0]["_dup_reason"] == "phone_exact"

def test_same_source_not_duplicate():
    df = pd.DataFrame([
        {"name": "焼鳥 鳥一郎", "address": "東京都新宿区歌舞伎町1-2-3", "phone": "03-1234-5678", "source": "google"},
        {"name": "焼鳥 鳥一郎", "address": "東京都新宿区歌舞伎町1-2-3", "phone": "03-1234-5678", "source": "google"}
    ])
    cleaned, duplicates, stats = run_dedup(df)
    
    # Should NOT be duplicate if source is the same
    assert len(cleaned) == 2
    assert len(duplicates) == 0
