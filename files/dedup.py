#!/usr/bin/env python3
"""
dedup.py  ―  飲食店データ 重複排除システム v2.0
================================================
対応ソース : Google Maps / 食べログ / Hot Pepper グルメ（拡張可能）
出力       : cleaned.csv / duplicates.csv / log.txt
"""

import argparse
import logging
import re
import sys
import time
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Optional

import pandas as pd
from rapidfuzz import fuzz

# ════════════════════════════════════════════════════════════
# 設定
# ════════════════════════════════════════════════════════════
SCORE_NAME_WEIGHT    = 0.6   # スコア合算: 店舗名の重み
SCORE_ADDR_WEIGHT    = 0.4   # スコア合算: 住所の重み
THRESH_NAME          = 85    # 店舗名 fuzzy 閾値 (%)
THRESH_ADDR          = 80    # 住所   fuzzy 閾値 (%)
THRESH_COMBINED      = 83    # 合算スコア閾値 (%)
THRESH_NAME_AREA     = 90    # 店舗名のみ + 同一エリア閾値 (%)

REQUIRED_COLUMNS     = {"name", "address", "phone", "url", "source"}
OPTIONAL_COLUMNS     = {"rating", "genre"}

# 「本店」「支店」などの揺れワード
BRANCH_WORDS = re.compile(
    r"(本店|支店|店舗|新館|別館|２号店|2号店|号店|[0-9０-９]+階|"
    r"[ａ-ｚＡ-Ｚa-zA-Z]館|east|west|north|south|east|west|店$)"
)

# ════════════════════════════════════════════════════════════
# ログ設定
# ════════════════════════════════════════════════════════════
def setup_logger(log_path: Path) -> logging.Logger:
    logger = logging.getLogger("dedup")
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S")

    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    return logger

logger: logging.Logger = None  # 後でセット


# ════════════════════════════════════════════════════════════
# 正規化ユーティリティ
# ════════════════════════════════════════════════════════════

def to_halfwidth(text: str) -> str:
    """全角 → 半角（NFKC 正規化）"""
    return unicodedata.normalize("NFKC", text)


def normalize_phone(raw: str) -> str:
    """
    電話番号正規化
    ・全角→半角
    ・+81 → 0
    ・数字のみ抽出（ハイフン除去）
    """
    if not raw or pd.isna(raw):
        return ""
    s = to_halfwidth(str(raw))
    s = re.sub(r"^\+81", "0", s)
    s = re.sub(r"[^\d]", "", s)
    return s.strip()


def extract_area_code(phone_norm: str) -> str:
    """市外局番を抽出（先頭3〜4桁）"""
    if len(phone_norm) >= 4:
        return phone_norm[:4]
    return phone_norm[:3] if len(phone_norm) >= 3 else phone_norm


def normalize_address(raw: str) -> str:
    """
    住所正規化
    ・全角→半角
    ・スペース除去
    ・ハイフン系統一
    ・小文字化
    """
    if not raw or pd.isna(raw):
        return ""
    s = to_halfwidth(str(raw))
    s = re.sub(r"\s+", "", s)
    s = re.sub(r"[ー－−‐―]", "-", s)   # ハイフン系統一
    s = re.sub(r"[^\w\d\-丁目番地号]", "", s)  # 不要記号除去
    return s.lower().strip()


def extract_municipality(addr_norm: str) -> str:
    """
    住所から市区町村レベルを抽出（ブロッキングキー）
    例: 兵庫県尼崎市 → 兵庫尼崎
    """
    if not addr_norm:
        return "__unknown__"
    m = re.search(
        r"(北海道|.{2,3}[都道府県])(.{2,6}[市区町村郡])?",
        addr_norm
    )
    if m:
        pref = (m.group(1) or "")[:4]
        city = (m.group(2) or "")[:5]
        return pref + city
    return addr_norm[:6] if len(addr_norm) >= 6 else addr_norm


def normalize_name(raw: str) -> str:
    """
    店舗名正規化
    ・全角→半角
    ・小文字化
    ・記号除去
    ・ブランチワード除去（本店/支店 など）→ ベース名抽出用
    """
    if not raw or pd.isna(raw):
        return ""
    s = to_halfwidth(str(raw))
    s = s.lower()
    # 括弧内（旧店名など）を除去
    s = re.sub(r"[（(【\[].*?[）)\]】]", "", s)
    # 記号除去（ハイフン・スペースは残す）
    s = re.sub(r"[^\w\s\-・]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def name_base(name_norm: str) -> str:
    """店舗名から「本店」「〇〇店」などの揺れ部分を除いたベース名"""
    return BRANCH_WORDS.sub("", name_norm).strip()


# ════════════════════════════════════════════════════════════
# データ読み込み
# ════════════════════════════════════════════════════════════

def load_csvs(paths: list[str]) -> pd.DataFrame:
    """複数CSVを読み込んで結合"""
    dfs = []
    for p in paths:
        path = Path(p)
        if not path.exists():
            logger.warning(f"ファイルが見つかりません: {path} → スキップ")
            continue
        try:
            df = pd.read_csv(path, encoding="utf-8-sig", dtype=str)
            df.columns = df.columns.str.strip().str.lower()

            # 必須カラムの補完
            for col in REQUIRED_COLUMNS | OPTIONAL_COLUMNS:
                if col not in df.columns:
                    df[col] = ""

            df["_src_file"] = path.name
            dfs.append(df)
            logger.info(f"  読み込み: {path.name}  {len(df):,} 件")
        except Exception as e:
            logger.error(f"  {path} 読み込み失敗: {e}")

    if not dfs:
        logger.error("有効なCSVが見つかりません。終了します。")
        sys.exit(1)

    combined = pd.concat(dfs, ignore_index=True)
    logger.info(f"  合計読み込み: {len(combined):,} 件")
    return combined


# ════════════════════════════════════════════════════════════
# 前処理（正規化カラム付与）
# ════════════════════════════════════════════════════════════

def preprocess(df: pd.DataFrame) -> pd.DataFrame:
    """全カラム正規化 + 補助カラム追加"""
    df = df.copy()
    for col in list(REQUIRED_COLUMNS | OPTIONAL_COLUMNS) + ["_src_file"]:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str)
        else:
            df[col] = ""

    df["_norm_phone"]   = df["phone"].apply(normalize_phone)
    df["_norm_address"] = df["address"].apply(normalize_address)
    df["_norm_name"]    = df["name"].apply(normalize_name)
    df["_base_name"]    = df["_norm_name"].apply(name_base)
    df["_area_code"]    = df["_norm_phone"].apply(
                              lambda p: extract_area_code(p) if p else "")
    df["_municipality"] = df["_norm_address"].apply(extract_municipality)

    # 重複管理フラグ
    df["_is_dup"]       = False
    df["_merged_to"]    = ""   # 統合先インデックス
    df["_dup_reason"]   = ""   # 統合理由
    df["_dup_score"]    = 0.0  # 類似スコア

    return df.reset_index(drop=True)


# ════════════════════════════════════════════════════════════
# 情報充実度スコア（統合時にどちらを残すか判断）
# ════════════════════════════════════════════════════════════

def richness_score(row: pd.Series) -> int:
    """電話・住所・名前の充実度を点数化（高い方を残す）"""
    score = 0
    if row["_norm_phone"]:                        score += 30
    if len(row["_norm_address"]) > 10:            score += 20
    elif row["_norm_address"]:                    score += 10
    if len(row["_norm_name"]) > 2:                score += 10
    if str(row.get("rating", "")).strip():        score += 5
    if str(row.get("genre", "")).strip():         score += 5
    # ソース優先度: tabelog > hotpepper > google（情報精度の経験則）
    src_bonus = {"tabelog": 3, "hotpepper": 2, "google": 1}
    score += src_bonus.get(str(row.get("source", "")), 0)
    return score


# ════════════════════════════════════════════════════════════
# ブロッキング（比較グループ生成）
# ════════════════════════════════════════════════════════════

def build_blocks(df: pd.DataFrame) -> dict[str, list[int]]:
    """
    同一グループ内のみ比較する（O(n^2)回避）
    ブロッキングキー:
      1. 市外局番（電話あり）
      2. 市区町村（電話なし）
    """
    blocks: dict[str, list[int]] = defaultdict(list)

    for idx, row in df.iterrows():
        phone = row["_norm_phone"]
        if phone and len(phone) >= 3:
            key = "phone_" + extract_area_code(phone)
        else:
            key = "addr_" + row["_municipality"]
        blocks[key].append(idx)

    # 統計ログ
    sizes = [len(v) for v in blocks.values()]
    logger.info(
        f"  ブロック数: {len(blocks):,}  "
        f"最大ブロックサイズ: {max(sizes) if sizes else 0}  "
        f"平均: {sum(sizes)/len(sizes):.1f}" if sizes else ""
    )
    return dict(blocks)


# ════════════════════════════════════════════════════════════
# 重複判定コア
# ════════════════════════════════════════════════════════════

def is_duplicate(df: pd.DataFrame, i: int, j: int) -> tuple[bool, str, float]:
    """
    レコード i と j が重複かを判定。
    戻り値: (重複か, 理由, スコア)
    """
    ri, rj = df.loc[i], df.loc[j]

    # ── ① 電話番号完全一致（最優先）──
    pi, pj = ri["_norm_phone"], rj["_norm_phone"]
    if pi and pj and pi == pj:
        return True, "phone_exact", 100.0

    # ── ② 店舗名 + 住所 fuzzy ──
    ni, nj = ri["_norm_name"], rj["_norm_name"]
    ai, aj = ri["_norm_address"], rj["_norm_address"]

    if ni and nj:
        name_sim = fuzz.token_sort_ratio(ni, nj)        # 語順揺れに強い
        name_base_sim = fuzz.token_sort_ratio(
            ri["_base_name"], rj["_base_name"]
        )
        name_score = max(name_sim, name_base_sim)

        if ai and aj:
            addr_sim = fuzz.partial_ratio(ai, aj)
            combined = name_score * SCORE_NAME_WEIGHT + addr_sim * SCORE_ADDR_WEIGHT

            if name_score >= THRESH_NAME and addr_sim >= THRESH_ADDR:
                return True, "name_addr_fuzzy", combined
            if combined >= THRESH_COMBINED:
                return True, "name_addr_score", combined

        # ── ③ 店舗名のみ高類似 + 同一エリア ──
        if name_score >= THRESH_NAME_AREA:
            area_i = ri["_municipality"]
            area_j = rj["_municipality"]
            if area_i and area_j and area_i == area_j:
                return True, "name_area", float(name_score)

    return False, "", 0.0


# ════════════════════════════════════════════════════════════
# 重複検出メイン
# ════════════════════════════════════════════════════════════

def detect_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """ブロッキング → fuzzy matching → 重複フラグ付与"""
    df = df.copy()
    blocks = build_blocks(df)

    total_comparisons = 0
    dup_counts = {"phone_exact": 0, "name_addr_fuzzy": 0,
                  "name_addr_score": 0, "name_area": 0}

    for block_key, indices in blocks.items():
        if len(indices) < 2:
            continue

        # ブロック内をリッチネス降順にソート（先頭が残るレコードになりやすい）
        block_sorted = sorted(
            indices,
            key=lambda idx: richness_score(df.loc[idx]),
            reverse=True
        )

        for pos_a, idx_a in enumerate(block_sorted):
            if df.at[idx_a, "_is_dup"]:
                continue

            for idx_b in block_sorted[pos_a + 1:]:
                if df.at[idx_b, "_is_dup"]:
                    continue

                total_comparisons += 1
                dup, reason, score = is_duplicate(df, idx_a, idx_b)

                if dup:
                    # idx_b を idx_a に統合（idx_a の方がリッチ）
                    df.at[idx_b, "_is_dup"]     = True
                    df.at[idx_b, "_merged_to"]  = str(idx_a)
                    df.at[idx_b, "_dup_reason"] = reason
                    df.at[idx_b, "_dup_score"]  = round(score, 1)
                    dup_counts[reason] = dup_counts.get(reason, 0) + 1

                    logger.info(
                        f"  [重複] {reason:<20} score={score:5.1f}  "
                        f"'{df.at[idx_b,'name'][:20]}' → '{df.at[idx_a,'name'][:20]}'"
                    )

    logger.info(f"  比較回数: {total_comparisons:,}")
    logger.info(f"  重複内訳: {dup_counts}")
    return df


# ════════════════════════════════════════════════════════════
# 出力
# ════════════════════════════════════════════════════════════

# 出力カラム定義（営業用）
OUTPUT_COLS = ["name", "address", "phone", "url", "source", "genre", "rating"]
DUP_COLS    = ["name", "address", "phone", "url", "source",
               "_merged_to", "_dup_reason", "_dup_score"]


def build_outputs(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """cleaned と duplicates の DataFrame を生成"""
    # 存在するカラムだけ選ぶ
    out_cols  = [c for c in OUTPUT_COLS if c in df.columns]
    dup_cols  = [c for c in DUP_COLS   if c in df.columns]

    cleaned    = df[~df["_is_dup"]][out_cols].reset_index(drop=True)
    duplicates = df[df["_is_dup"]][dup_cols].reset_index(drop=True)

    return cleaned, duplicates


def save_csv(df: pd.DataFrame, path: Path) -> None:
    df.to_csv(path, index=False, encoding="utf-8-sig")
    logger.info(f"  保存: {path}  ({len(df):,} 件)")


# ════════════════════════════════════════════════════════════
# サマリーログ出力
# ════════════════════════════════════════════════════════════

def write_summary(
    df_raw: pd.DataFrame,
    cleaned: pd.DataFrame,
    duplicates: pd.DataFrame,
    elapsed: float,
    log_path: Path,
) -> None:
    dup_rate = len(duplicates) / len(df_raw) * 100 if len(df_raw) else 0

    lines = [
        "=" * 56,
        "  飲食店データ 重複排除システム  処理サマリー",
        "=" * 56,
        f"  処理時間      : {elapsed:.2f} 秒",
        f"  入力件数      : {len(df_raw):>8,} 件",
        f"  重複件数      : {len(duplicates):>8,} 件",
        f"  出力件数      : {len(cleaned):>8,} 件",
        f"  重複率        : {dup_rate:>7.1f} %",
        "-" * 56,
    ]

    # ソース別内訳
    if "source" in df_raw.columns:
        lines.append("  ソース別内訳（入力）:")
        for src, cnt in df_raw["source"].value_counts().items():
            lines.append(f"    {str(src):<20} {cnt:>6,} 件")
        lines.append("-" * 56)

    # 重複理由内訳
    if "_dup_reason" in duplicates.columns and len(duplicates):
        lines.append("  重複理由内訳:")
        for reason, cnt in duplicates["_dup_reason"].value_counts().items():
            lines.append(f"    {str(reason):<22} {cnt:>6,} 件")
        lines.append("-" * 56)

    lines.append("=" * 56)
    summary = "\n".join(lines)
    print(summary)

    with open(log_path, "a", encoding="utf-8") as f:
        f.write("\n" + summary + "\n")


# ════════════════════════════════════════════════════════════
# CLI
# ════════════════════════════════════════════════════════════

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="飲食店データ 重複排除システム",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python dedup.py data1.csv data2.csv data3.csv
  python dedup.py *.csv --out-dir results/
  python dedup.py input.csv --name-thresh 90 --addr-thresh 85
        """,
    )
    p.add_argument("inputs", nargs="+", metavar="CSV",
                   help="入力CSVファイル（複数指定可）")
    p.add_argument("--out-dir", default=".",
                   help="出力ディレクトリ (default: カレント)")
    p.add_argument("--name-thresh", type=int, default=THRESH_NAME,
                   help=f"店舗名 fuzzy 閾値 (default: {THRESH_NAME})")
    p.add_argument("--addr-thresh", type=int, default=THRESH_ADDR,
                   help=f"住所 fuzzy 閾値 (default: {THRESH_ADDR})")
    p.add_argument("--name-area-thresh", type=int, default=THRESH_NAME_AREA,
                   help=f"店舗名+エリア閾値 (default: {THRESH_NAME_AREA})")
    return p.parse_args()


def main() -> None:
    global THRESH_NAME, THRESH_ADDR, THRESH_NAME_AREA, logger

    args   = parse_args()
    outdir = Path(args.out_dir)
    outdir.mkdir(parents=True, exist_ok=True)

    log_path = outdir / "log.txt"
    logger   = setup_logger(log_path)

    # 閾値上書き
    THRESH_NAME      = args.name_thresh
    THRESH_ADDR      = args.addr_thresh
    THRESH_NAME_AREA = args.name_area_thresh

    logger.info("=" * 56)
    logger.info("  飲食店データ 重複排除システム 開始")
    logger.info("=" * 56)

    start = time.perf_counter()

    # ① 読み込み
    logger.info("[1/5] CSV 読み込み")
    df_raw = load_csvs(args.inputs)

    # ② 正規化
    logger.info("[2/5] 正規化")
    df = preprocess(df_raw)

    # ③④ ブロッキング → fuzzy matching
    logger.info("[3/5] ブロッキング & 重複検出")
    df = detect_duplicates(df)

    # ⑤⑥ 統合 & 出力データ生成
    logger.info("[4/5] 出力データ生成")
    cleaned, duplicates = build_outputs(df)

    # ⑦ CSV保存
    logger.info("[5/5] CSV 保存")
    save_csv(cleaned,    outdir / "cleaned.csv")
    save_csv(duplicates, outdir / "duplicates.csv")

    elapsed = time.perf_counter() - start

    # サマリー
    write_summary(df_raw, cleaned, duplicates, elapsed, log_path)


if __name__ == "__main__":
    main()
