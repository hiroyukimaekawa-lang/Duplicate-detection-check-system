import unicodedata
import re
import pandas as pd

def to_halfwidth(text: str) -> str:
    return unicodedata.normalize("NFKC", text)

def kanji_to_arabic(text: str) -> str:
    """
    Converts Kanji numbers (一, 二, 十, etc.) to Arabic numbers (1, 2, 10, etc.)
    ONLY when they are likely part of a count or address structure (e.g., 丁目).
    """
    kanji_map = {
        '〇': '0', '一': '1', '二': '2', '三': '3', '四': '4',
        '五': '5', '六': '6', '七': '7', '八': '8', '九': '9',
    }
    
    def replace_kanji_num(s):
        val = 0
        if not s: return ""
        # Handle 十, 百
        if '百' in s:
            parts = s.split('百')
            val += (int(kanji_map.get(parts[0], parts[0]) if parts[0] else 1)) * 100
            s = parts[1]
        if '十' in s:
            parts = s.split('十')
            # Handle cases like 二十, 三十 or just 十
            prefix = parts[0]
            if prefix:
                prefix_val = int(kanji_map.get(prefix, prefix))
            else:
                prefix_val = 1
            val += prefix_val * 10
            s = parts[1]
        if s:
            val += int(kanji_map.get(s, s))
        return str(val)

    # Only convert if followed by 丁目, 番地, 番, or at the end of a string segment
    def cb(m):
        num_part = m.group(1)
        suffix = m.group(2)
        return replace_kanji_num(num_part) + suffix

    # Match Kanji numbers followed by address suffixes
    text = re.sub(r'([〇一二三四五六七八九十百]+)(丁目|番地?|号)', cb, text)
    
    return text

def normalize_name(text: str) -> str:
    """
    Normalizes restaurant names.
    1. NFKC normalization (Full-width to half-width)
    2. Lowercase unification
    3. Remove corporate suffixes (株式会社, 有限会社, (株), etc.)
    4. Remove decoration symbols (【】, ★, ♪, etc.)
    5. Collapse multiple spaces and trim
    6. Remove "The", "ザ・", "ザ " from the beginning
    """
    if not text or not isinstance(text, str):
        return ""
    
    # 1. NFKC
    s = unicodedata.normalize("NFKC", text)
    
    # 2. Lowercase
    s = s.lower()
    
    # 3. Remove corporate suffixes
    corpo_regex = re.compile(
        r"(株式会社|有限会社|合同会社|特定非営利活動法人|一般社団法人|一般財団法人|"
        r"\(株\)|（株）|【株】|㈱|有限|合資|合名|llc|inc\.|corp\.)",
        re.IGNORECASE
    )
    s = corpo_regex.sub("", s)
    
    # 4. Remove decoration symbols
    s = re.sub(r"[【】★♪☆◆◇■□●○◎△▽▼▲<>\[\]\(\)（）]", " ", s)
    
    # Special characters like punctuation
    s = re.sub(r"[^\w\s\-・]", " ", s)
    
    # 5. Collapse spaces and trim
    s = re.sub(r"\s+", " ", s).strip()
    
    # 6. Remove "The", "ザ・", "ザ " from the beginning
    s = re.sub(r"^(the\s|ザ・|ザ\s|ザ)", "", s)
    
    return s.strip()

def normalize_address(text: str) -> str:
    """
    Normalizes addresses.
    1. NFKC normalization
    2. Unify prefecture names (東京 -> 東京都, etc.)
    3. Unify block/lot numbers (3丁目4番5号 -> 3-4-5)
    4. Remove building names and floor numbers
    5. Final cleanup
    """
    if not text or not isinstance(text, str):
        return ""
    
    # 1. NFKC
    s = unicodedata.normalize("NFKC", text)
    s = s.replace("　", " ").strip()
    
    # 2. Unify prefecture names (Simplified common cases)
    prefectures = ["東京都", "大阪府", "京都府", "北海道"]
    for pref in prefectures:
        short = pref[:-1]
        if s.startswith(short) and not s.startswith(pref):
            s = pref + s[len(short):]
            
    # 3. Unify block/lot numbers
    # Convert "三丁目" to "3丁目"
    s = kanji_to_arabic(s)
    
    # Replace "丁目", "番地", "番", "号" with hyphens
    s = re.sub(r"([0-9]+)丁目", r"\1-", s)
    s = re.sub(r"([0-9]+)番地?", r"\1-", s)
    s = re.sub(r"([0-9]+)号", r"\1", s)
    
    # Clean up multiple hyphens and trailing hyphens
    s = re.sub(r"-+", "-", s)
    s = s.strip("-")
    
    # 4. Remove building names and floor numbers
    # Usually building info starts after the address numbers
    m = re.search(r"([0-9]+[0-9\-]*)", s)
    if m:
        end_idx = m.end()
        remaining = s[end_idx:]
        # Look for the end of the number/hyphen sequence
        # Common building keywords: ビル, タワー, ビルディング, BLDG, 階, F
        # Also handle spaces
        split_match = re.search(r"(\s|ビル|タワー|ビルディング|bldg|階|f)", remaining, re.IGNORECASE)
        if split_match:
            s = s[:end_idx + split_match.start()]
    
    # Final cleanup of symbols
    s = re.sub(r"[ー－−‐―]", "-", s)
    s = re.sub(r"[^\w\d\-]", "", s)
    
    return s.lower().strip()

def extract_municipality(address: str) -> tuple[str, str]:
    """
    Extracts (prefecture, city) from address.
    Handles designated cities like "大阪市北区".
    """
    if not address:
        return ("", "")
    
    # NFKC first
    address = unicodedata.normalize("NFKC", address)
    
    # 1. Extract Prefecture
    pref_match = re.match(r"(北海道|.{2,3}[都道府県])", address)
    if not pref_match:
        return (address[:3], address[3:9]) if len(address) > 9 else (address, "")
    
    pref = pref_match.group(1)
    rest = address[len(pref):]
    
    # 2. Extract Municipality
    # Try to match "City + Ward" first (Designated cities)
    city_ward_match = re.match(r"(.{2,6}?[市])(.{1,6}?[区])", rest)
    if city_ward_match:
        return (pref, city_ward_match.group(1) + city_ward_match.group(2))
    
    # Otherwise match the first occurrence of City/Ward/Town/Village/County
    muni_match = re.match(r"(.{2,8}?[市区町村郡])", rest)
    if muni_match:
        return (pref, muni_match.group(1))
    
    return (pref, rest[:6])
