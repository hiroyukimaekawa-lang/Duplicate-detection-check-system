import pytest
import pandas as pd
from ..privacy import mask_phone, mask_email, apply_privacy_masking

def test_mask_phone():
    assert mask_phone("09012345678") == "090****5678"
    assert mask_phone("03-1234-5678") == "03-*****5678"
    assert mask_phone("invalid") == "invalid"

def test_mask_email():
    assert mask_email("test@example.com") == "t***@example.com"
    assert mask_email("a@b.com") == "*@b.com"

def test_apply_privacy_masking():
    df = pd.DataFrame([
        {"name": "Rest A", "phone": "09011112222", "representative": "田中太郎"},
        {"name": "Rest B", "phone": "0311112222", "representative": "佐藤花子"}
    ])
    
    masked = apply_privacy_masking(df)
    
    assert masked["phone"].iloc[0] == "090****2222"
    assert masked["representative"].iloc[0] == "田**"
    assert masked["representative"].iloc[1] == "佐**"
    # Name should NOT be masked by default unless specified
    assert masked["name"].iloc[0] == "Rest A"
