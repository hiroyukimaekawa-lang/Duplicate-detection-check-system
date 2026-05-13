import sys
import os
import pandas as pd
import json

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from api.filters import filter_out_unwanted
from api.dedup_engine import run_dedup

def test_full_pipeline():
    # Sample data
    data = [
        # Chain stores
        {"name": "マクドナルド 渋谷店", "address": "東京都渋谷区...", "phone": "03-1111-1111", "url": "...", "source": "google"},
        {"name": "マクドナルド 新宿店", "address": "東京都新宿区...", "phone": "03-2222-2222", "url": "...", "source": "google"},
        # Duplicate pair
        {"name": "サントリーホール", "address": "東京都港区赤坂1-13-1", "phone": "03-3505-1001", "url": "...", "source": "tabelog"},
        {"name": "Suntory Hall", "address": "東京都港区赤坂1丁目13-1", "phone": "0335051001", "url": "...", "source": "hotpepper"},
        # Normal store
        {"name": "独自店舗 A", "address": "東京都千代田区...", "phone": "03-9999-9999", "url": "...", "source": "google"},
        # Mall example
        {"name": "三越 銀座店", "address": "東京都中央区銀座4-6-16", "phone": "03-3562-1111", "url": "...", "source": "google"},
    ]
    
    df = pd.DataFrame(data)
    df.columns = df.columns.str.lower()
    
    print("--- 1. Initial Data ---")
    print(df[["name", "source"]])
    
    # 1. Filter out chains and malls
    # In this test, we exclude chains
    filtered_df, excluded_df, filter_stats = filter_out_unwanted(df, exclude_chains=True)
    
    print("\n--- 2. Filter Results ---")
    print(f"Filter Stats: {filter_stats}")
    print("Excluded (Chains/Malls):")
    print(excluded_df[["name", "_filter_reason"]])
    print("Filtered (To be deduped):")
    print(filtered_df[["name", "source"]])
    
    # 2. Deduplication
    cleaned_df, duplicates_df, dedup_stats = run_dedup(filtered_df, criteria=["name", "phone", "address"])
    
    print("\n--- 3. Dedup Results ---")
    print(f"Dedup Stats: {dedup_stats}")
    print("Cleaned List:")
    print(cleaned_df[["name", "source"]])
    print("Duplicates Found:")
    print(duplicates_df[["name", "_dup_reason", "_dup_score"]])

if __name__ == "__main__":
    test_full_pipeline()
