import pytest
import pandas as pd
from ..model import DedupModel
from ..dedup_engine import is_duplicate, preprocess

def test_ml_model_prediction():
    model = DedupModel()
    assert model.model is not None, "Model should be loaded"
    
    # Test a known duplicate pair from gold dataset
    row_a = {"name": "焼鳥 鳥一郎", "address": "東京都新宿区歌舞伎町1-2-3", "phone": "03-1234-5678", "source": "google"}
    row_b = {"name": "鳥一郎 新宿店", "address": "新宿区歌舞伎町1丁目2番3号", "phone": "0312345678", "source": "tabelog"}
    
    prob = model.predict_proba(row_a, row_b)
    print(f"Duplicate Probability: {prob:.4f}")
    assert prob >= 0.7
    
    # Test a known non-duplicate pair
    row_c = {"name": "マクドナルド 渋谷店", "address": "東京都渋谷区", "phone": "03-0000-0001", "source": "google"}
    row_d = {"name": "マクドナルド 新宿店", "address": "東京都新宿区", "phone": "03-0000-0002", "source": "tabelog"}
    
    prob_non = model.predict_proba(row_c, row_d)
    print(f"Non-Duplicate Probability: {prob_non:.4f}")
    assert prob_non < 0.5

def test_dedup_engine_with_ml():
    df = pd.DataFrame([
        {"name": "焼鳥 鳥一郎", "address": "東京都新宿区歌舞伎町1-2-3", "phone": "03-1234-5678", "source": "google"},
        {"name": "鳥一郎 新宿店", "address": "新宿区歌舞伎町1丁目2番3号", "phone": "0312345678", "source": "tabelog"}
    ])
    df = preprocess(df)
    
    model = DedupModel()
    dup, reason, score = is_duplicate(df, 0, 1, model=model)
    
    assert dup is True
    assert reason == "ml_model"
    assert score >= 70.0
