import pandas as pd
import os
import re

# Master lists cache
_chains_master = []
_mall_master = []

def normalize(text):
    if pd.isna(text):
        return ""
    # Convert to lowercase and remove spaces/full-width spaces
    return str(text).lower().replace(" ", "").replace("　", "").strip()

def load_master_csv(path: str) -> list:
    if not os.path.exists(path):
        return []
    try:
        df = pd.read_csv(path, encoding='utf-8')
        # Check if 'name' column exists
        if 'name' not in df.columns:
            # Fallback to the first column if 'name' doesn't exist
            if len(df.columns) > 0:
                col = df.columns[0]
            else:
                return []
        else:
            col = 'name'
            
        # Extract, remove NaN, normalize
        names = df[col].dropna().apply(normalize)
        # Filter out empty strings and return unique list
        return list(set([n for n in names if n]))
    except Exception as e:
        print(f"Error loading master CSV {path}: {e}")
        return []

def initialize_masters():
    global _chains_master, _mall_master
    base_dir = os.path.dirname(os.path.abspath(__file__))
    chains_path = os.path.join(base_dir, "masters", "chains_master.csv")
    mall_path = os.path.join(base_dir, "masters", "mall_master.csv")
    
    _chains_master = load_master_csv(chains_path)
    _mall_master = load_master_csv(mall_path)

# Initialize on module import
initialize_masters()

def filter_out_unwanted(df: pd.DataFrame, exclude_chains: bool):
    """
    Filter out commercial facilities (malls) and chains (if exclude_chains is True).
    Returns (filtered_df, excluded_df, stats)
    """
    if df.empty:
        return df, pd.DataFrame(), {
            "total": 0, "after_filter": 0, "excluded": 0, "mall_excluded": 0, "chain_excluded": 0
        }

    df = df.copy()
    
    # Initialize flags
    df['is_mall'] = False
    df['is_chain_master'] = False
    df['_filter_reason'] = ""
    
    # Pre-normalize columns for checking
    # Safely get columns, default to empty string if missing
    norm_names = df.get('name', pd.Series([""] * len(df))).apply(normalize)
    norm_addrs = df.get('address', pd.Series([""] * len(df))).apply(normalize)
    
    # 1. Mall Check
    if _mall_master:
        # Check if any mall keyword is in address or name
        for mall_kw in _mall_master:
            if not mall_kw: continue
            mall_mask = norm_names.str.contains(mall_kw, regex=False, na=False) | norm_addrs.str.contains(mall_kw, regex=False, na=False)
            df.loc[mall_mask, 'is_mall'] = True
            # Only set reason if it's not already set
            df.loc[mall_mask & (df['_filter_reason'] == ""), '_filter_reason'] = "mall_excluded"

    # 2. Chain Check (Master CSV)
    if _chains_master:
        for chain_kw in _chains_master:
            if not chain_kw: continue
            chain_mask = norm_names.str.contains(chain_kw, regex=False, na=False)
            df.loc[chain_mask, 'is_chain_master'] = True
            df.loc[chain_mask & (df['_filter_reason'] == ""), '_filter_reason'] = "chain_excluded"
            
    # Also incorporate the original deduplication engine's chain logic if exclude_chains is true?
    # Actually, the user says: exclude_chains == True かつ is_chain == True → 除外
    # So we'll use 'is_chain_master' for the master-based chain check.
    
    # 3. Create filtering mask
    # Malls are always excluded. Chains are excluded ONLY IF exclude_chains is True.
    exclude_mask = df['is_mall']
    if exclude_chains:
        exclude_mask = exclude_mask | df['is_chain_master']
        
    # Split the dataframe
    filtered_df = df[~exclude_mask].copy()
    excluded_df = df[exclude_mask].copy()
    
    # Stats
    mall_count = int(df['is_mall'].sum())
    # Chain count (only those excluded purely because they are chains, not malls)
    chain_count = int((df['is_chain_master'] & ~df['is_mall']).sum()) if exclude_chains else 0
    
    stats = {
        "total": len(df),
        "after_filter": len(filtered_df),
        "excluded": len(excluded_df),
        "mall_excluded": mall_count,
        "chain_excluded": chain_count
    }
    
    return filtered_df, excluded_df, stats
