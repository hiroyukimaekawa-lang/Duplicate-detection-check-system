import logging
import re
import unicodedata
from collections import defaultdict
from typing import List, Dict, Tuple, Optional
import pandas as pd
from rapidfuzz import fuzz

# Constants from original dedup.py
SCORE_NAME_WEIGHT = 0.6
SCORE_ADDR_WEIGHT = 0.4
THRESH_NAME = 85
THRESH_ADDR = 80
THRESH_COMBINED = 83
THRESH_NAME_AREA = 90

REQUIRED_COLUMNS = {"name", "address", "phone", "url", "source"}
OPTIONAL_COLUMNS = {"rating", "genre"}

BRANCH_WORDS = re.compile(
    r"(本店|支店|店舗|新館|別館|２号店|2号店|号店|[0-9０-９]+階|"
    r"[ａ-ｚＡ-Ｚa-zA-Z]館|east|west|north|south|店$)"
)

logger = logging.getLogger("dedup_engine")

def to_halfwidth(text: str) -> str:
    return unicodedata.normalize("NFKC", text)

def normalize_phone(raw: str) -> str:
    if not raw or pd.isna(raw):
        return ""
    s = to_halfwidth(str(raw))
    s = re.sub(r"^\+81", "0", s)
    s = re.sub(r"[^\d]", "", s)
    return s.strip()

def extract_area_code(phone_norm: str) -> str:
    if len(phone_norm) >= 4:
        return phone_norm[:4]
    return phone_norm[:3] if len(phone_norm) >= 3 else phone_norm

def normalize_address(raw: str) -> str:
    if not raw or pd.isna(raw):
        return ""
    s = to_halfwidth(str(raw))
    s = re.sub(r"\s+", "", s)
    s = re.sub(r"[ー－−‐―]", "-", s)
    s = re.sub(r"[^\w\d\-丁目番地号]", "", s)
    return s.lower().strip()

def extract_municipality(addr_norm: str) -> str:
    if not addr_norm:
        return "__unknown__"
    # Capture Prefecture + Municipality (stops at City/Town/Village level)
    m = re.search(r"(北海道|.{2,3}[都道府県])(.{2,6}[市区町村郡])", addr_norm)
    if m:
        return m.group(1) + m.group(2)
    return addr_norm[:6] if len(addr_norm) >= 6 else addr_norm

def normalize_name(raw: str) -> str:
    if not raw or pd.isna(raw):
        return ""
    s = to_halfwidth(str(raw))
    s = s.lower()
    s = re.sub(r"[（(【\[].*?[）)\]】]", "", s)
    s = re.sub(r"[^\w\s\-・]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def name_base(name_norm: str) -> str:
    return BRANCH_WORDS.sub("", name_norm).strip()

def preprocess(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in list(REQUIRED_COLUMNS | OPTIONAL_COLUMNS):
        if col not in df.columns:
            df[col] = ""
        df[col] = df[col].fillna("").astype(str)

    df["_norm_phone"] = df["phone"].apply(normalize_phone)
    df["_norm_address"] = df["address"].apply(normalize_address)
    df["_norm_name"] = df["name"].apply(normalize_name)
    df["_base_name"] = df["_norm_name"].apply(name_base)
    df["_area_code"] = df["_norm_phone"].apply(lambda p: extract_area_code(p) if p else "")
    df["_municipality"] = df["_norm_address"].apply(extract_municipality)

    # Chain Detection
    df["brand"] = df["_base_name"]
    brand_counts = df["brand"].value_counts()
    
    # Keyword-based: if original name had branch words removed, it's likely a chain
    # Also frequency-based: count >= 5
    df["is_chain"] = df.apply(
        lambda r: (brand_counts[r["brand"]] >= 5) or (r["_norm_name"] != r["_base_name"]),
        axis=1
    )

    # Check if phone number is valid (10-11 digits)
    df["is_phone_invalid"] = df["_norm_phone"].apply(lambda x: len(x) < 10)

    df["_is_dup"] = False
    df["_merged_to"] = ""
    df["_dup_reason"] = ""
    df["_dup_score"] = 0.0

    return df.reset_index(drop=True)

def richness_score(row: pd.Series) -> int:
    score = 0
    if row["_norm_phone"]: score += 30
    if len(row["_norm_address"]) > 10: score += 20
    elif row["_norm_address"]: score += 10
    if len(row["_norm_name"]) > 2: score += 10
    if str(row.get("rating", "")).strip(): score += 5
    if str(row.get("genre", "")).strip(): score += 5
    src_bonus = {"tabelog": 3, "hotpepper": 2, "google": 1}
    score += src_bonus.get(str(row.get("source", "")), 0)
    return score

def build_blocks(df: pd.DataFrame) -> Dict[str, List[int]]:
    blocks = defaultdict(list)
    for idx, row in df.iterrows():
        phone = row["_norm_phone"]
        if phone and len(phone) >= 3:
            key = "phone_" + extract_area_code(phone)
        else:
            key = "addr_" + row["_municipality"]
        blocks[key].append(idx)
    return dict(blocks)

def is_duplicate(df: pd.DataFrame, i: int, j: int, criteria: List[str] = None) -> Tuple[bool, str, float]:
    if criteria is None:
        criteria = ["phone", "name", "address"] # Default behavior

    ri, rj = df.loc[i], df.loc[j]
    
    # 1. Same source skip
    if ri["source"] == rj["source"]:
        return False, "", 0.0

    # 2. Chain logic
    # If both are chains, they must have the same address (or very close) to be considered duplicates
    is_chain_i = ri["is_chain"]
    is_chain_j = rj["is_chain"]

    pi, pj = ri["_norm_phone"], rj["_norm_phone"]
    ai, aj = ri["_norm_address"], rj["_norm_address"]
    ni, nj = ri["_norm_name"], rj["_norm_name"]

    # Special handling for chains: strictly require same address/phone
    if is_chain_i and is_chain_j:
        if "phone" in criteria and pi and pj and pi == pj:
            return True, "chain_phone_exact", 100.0
        if ai and aj and ("address" in criteria or "name" in criteria):
            addr_sim = fuzz.partial_ratio(ai, aj)
            if addr_sim >= THRESH_ADDR:
                name_sim = fuzz.token_sort_ratio(ni, nj)
                if name_sim >= THRESH_NAME:
                    return True, "chain_addr_name_match", float(addr_sim)
        return False, "", 0.0

    # Normal deduplication logic
    
    # Phone match
    if "phone" in criteria:
        if pi and pj and pi == pj:
            return True, "phone_exact", 100.0

    # Name and Address logic
    if ni and nj:
        name_sim = fuzz.token_sort_ratio(ni, nj)
        name_base_sim = fuzz.token_sort_ratio(ri["_base_name"], rj["_base_name"])
        name_score = max(name_sim, name_base_sim)

        # Combined Name + Address
        if "name" in criteria and "address" in criteria:
            if ai and aj:
                addr_sim = fuzz.partial_ratio(ai, aj)
                combined = name_score * SCORE_NAME_WEIGHT + addr_sim * SCORE_ADDR_WEIGHT
                if name_score >= THRESH_NAME and addr_sim >= THRESH_ADDR:
                    return True, "name_addr_fuzzy", combined
                if combined >= THRESH_COMBINED:
                    return True, "name_addr_score", combined
            
            # If address is missing but name is very strong in same area
            if name_score >= THRESH_NAME_AREA:
                area_i = ri["_municipality"]
                area_j = rj["_municipality"]
                if area_i and area_j and area_i == area_j:
                    return True, "name_area", float(name_score)
        
        # Only Name
        elif "name" in criteria:
            if name_score >= THRESH_NAME_AREA: # Use higher threshold for name-only
                area_i = ri["_municipality"]
                area_j = rj["_municipality"]
                if area_i and area_j and area_i == area_j:
                    return True, "name_only_match", float(name_score)

        # Only Address
        elif "address" in criteria:
            if ai and aj:
                addr_sim = fuzz.partial_ratio(ai, aj)
                if addr_sim >= 95: # Very high threshold for address-only
                    return True, "address_only_match", float(addr_sim)

    return False, "", 0.0

def run_dedup(df: pd.DataFrame, criteria: List[str] = None) -> Tuple[pd.DataFrame, pd.DataFrame, Dict]:
    df = preprocess(df)
    blocks = build_blocks(df)
    
    dup_counts = defaultdict(int)

    for block_key, indices in blocks.items():
        if len(indices) < 2: continue
        block_sorted = sorted(indices, key=lambda idx: richness_score(df.loc[idx]), reverse=True)

        for pos_a, idx_a in enumerate(block_sorted):
            if df.at[idx_a, "_is_dup"]: continue
            for idx_b in block_sorted[pos_a + 1:]:
                if df.at[idx_b, "_is_dup"]: continue
                
                dup, reason, score = is_duplicate(df, idx_a, idx_b, criteria)
                if dup:
                    df.at[idx_b, "_is_dup"] = True
                    df.at[idx_b, "_merged_to"] = str(idx_a)
                    df.at[idx_b, "_dup_reason"] = reason
                    df.at[idx_b, "_dup_score"] = round(score, 1)
                    dup_counts[reason] += 1

    # Add columns to output
    df["municipality"] = df["_municipality"]
    
    # Calculate counts for sorting
    counts = df["municipality"].value_counts().to_dict()
    df["_area_count"] = df["municipality"].map(counts)

    out_cols = ["name", "brand", "is_chain", "address", "phone", "url", "source", "genre", "rating", "municipality", "is_phone_invalid"]
    dup_cols = ["name", "brand", "is_chain", "address", "phone", "url", "source", "_merged_to", "_dup_reason", "_dup_score", "municipality", "is_phone_invalid"]

    # Sort by area count (descending), then municipality name, then phone validity
    cleaned = df[~df["_is_dup"]][out_cols].copy()
    cleaned["_count"] = cleaned["municipality"].map(cleaned["municipality"].value_counts())
    cleaned = cleaned.sort_values(["_count", "municipality", "is_phone_invalid"], ascending=[False, True, True]).drop(columns=["_count"]).reset_index(drop=True)
    
    duplicates = df[df["_is_dup"]][dup_cols].copy()
    duplicates["_count"] = duplicates["municipality"].map(duplicates["municipality"].value_counts())
    duplicates = duplicates.sort_values(["_count", "municipality", "is_phone_invalid"], ascending=[False, True, True]).drop(columns=["_count"]).reset_index(drop=True)

    summary = {
        "input_count": len(df),
        "dup_count": len(duplicates),
        "output_count": len(cleaned),
        "chain_count": int(cleaned["is_chain"].sum()),
        "normal_count": int((~cleaned["is_chain"]).sum()),
        "dup_rate": round(len(duplicates) / len(df) * 100, 1) if len(df) else 0,
        "reasons": dict(dup_counts),
        "invalid_phone_count": int(cleaned["is_phone_invalid"].sum()),
        "municipality_counts": cleaned["municipality"].value_counts().to_dict()
    }

    return cleaned, duplicates, summary
