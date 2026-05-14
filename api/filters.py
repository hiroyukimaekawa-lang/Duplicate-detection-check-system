import pandas as pd
import os
import re

# Master lists cache
_chains_master = []
_mall_master = []

from .normalizer import normalize_name as normalize

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

def _build_chain_pattern(keyword: str) -> str:
    """
    Build a regex pattern for matching a chain store keyword in a normalized name.
    
    For short keywords (< 4 chars like ガスト, 大戸屋):
      - Must be at the START of the name, or be the ENTIRE name,
        or be followed by a store-related suffix (店, 支店, space, etc.)
    For longer keywords (>= 4 chars like マクドナルド, ケンタッキー):
      - Simple 'contains' is sufficient as false positives are rare.
    """
    escaped = re.escape(keyword)
    if len(keyword) < 4:
        # Short keyword: require word boundary context
        # Match if: start-of-string OR preceded by space/・
        # AND: end-of-string OR followed by space/・/store suffix/digits/location
        return rf"(?:^|[\s・　]){escaped}(?:$|[\s・　0-9]|店|支店|号店|本店|分店|東口|西口|南口|北口|駅前|[市区町村])"
    else:
        # Longer keyword: simple contains is safe
        return escaped


def _build_mall_pattern(keyword: str) -> str:
    """
    Build a regex pattern for matching a mall/commercial facility keyword.
    Malls are checked against both name and address, so we use contains.
    """
    return re.escape(keyword)


# Pre-compiled pattern caches (populated on first use)
_chain_patterns_cache = None
_mall_patterns_cache = None


def _get_chain_patterns():
    global _chain_patterns_cache
    if _chain_patterns_cache is None:
        _chain_patterns_cache = []
        for kw in _chains_master:
            if not kw:
                continue
            try:
                pattern = _build_chain_pattern(kw)
                _chain_patterns_cache.append((kw, re.compile(pattern)))
            except re.error:
                continue
    return _chain_patterns_cache


def _get_mall_patterns():
    global _mall_patterns_cache
    if _mall_patterns_cache is None:
        _mall_patterns_cache = []
        for kw in _mall_master:
            if not kw:
                continue
            try:
                pattern = _build_mall_pattern(kw)
                _mall_patterns_cache.append((kw, re.compile(pattern)))
            except re.error:
                continue
    return _mall_patterns_cache


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
    df['_matched_chain'] = ""  # Track which chain keyword matched (for debugging)
    
    # Pre-normalize columns for checking
    norm_names = df.get('name', pd.Series([""] * len(df))).apply(normalize)
    norm_addrs = df.get('address', pd.Series([""] * len(df))).apply(normalize)
    
    # 1. Mall Check — uses simple contains (malls appear in address too)
    for kw, pattern in _get_mall_patterns():
        mall_name_mask = norm_names.str.contains(pattern, regex=True, na=False)
        mall_addr_mask = norm_addrs.str.contains(pattern, regex=True, na=False)
        mall_mask = mall_name_mask | mall_addr_mask
        df.loc[mall_mask, 'is_mall'] = True
        df.loc[mall_mask & (df['_filter_reason'] == ""), '_filter_reason'] = "mall_excluded"

    # 2. Chain Check — uses strict regex patterns to avoid false positives
    if exclude_chains:
        for kw, pattern in _get_chain_patterns():
            chain_mask = norm_names.str.contains(pattern, regex=True, na=False)
            df.loc[chain_mask, 'is_chain_master'] = True
            df.loc[chain_mask & (df['_filter_reason'] == ""), '_filter_reason'] = "chain_excluded"
            df.loc[chain_mask & (df['_matched_chain'] == ""), '_matched_chain'] = kw
    
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
    chain_count = int((df['is_chain_master'] & ~df['is_mall']).sum()) if exclude_chains else 0
    
    stats = {
        "total": len(df),
        "after_filter": len(filtered_df),
        "excluded": len(excluded_df),
        "mall_excluded": mall_count,
        "chain_excluded": chain_count
    }
    
    return filtered_df, excluded_df, stats
