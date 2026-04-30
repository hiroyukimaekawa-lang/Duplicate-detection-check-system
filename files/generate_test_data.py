#!/usr/bin/env python3
"""
generate_test_data.py  ― テストデータ生成スクリプト
実際の重複パターンを含むCSVを生成する
"""
import random
import csv
import unicodedata

random.seed(42)

PREFECTURES = ["東京都", "大阪府", "兵庫県", "愛知県", "福岡県"]
CITIES = {
    "東京都": ["渋谷区", "新宿区", "品川区", "港区", "中野区"],
    "大阪府": ["大阪市北区", "大阪市中央区", "堺市", "豊中市"],
    "兵庫県": ["尼崎市", "神戸市中央区", "西宮市", "姫路市"],
    "愛知県": ["名古屋市中区", "名古屋市栄区", "豊田市"],
    "福岡県": ["福岡市博多区", "福岡市中央区", "北九州市"],
}
GENRES = ["焼肉", "寿司", "ラーメン", "カフェ", "居酒屋", "イタリアン", "中華"]
SOURCES = ["google", "tabelog", "hotpepper"]
SHOP_NAMES = [
    "やきにく太郎", "寿司花子", "ラーメン次郎", "カフェ青山",
    "居酒屋龍", "イタリアンVita", "中華楼", "焼肉ホルモン王",
    "うどん讃岐屋", "天ぷら金沢", "とんかつ武蔵", "鮨さかな",
    "パスタNapoli", "焼き鳥伝助", "鍋料理ゆず", "串カツ道頓堀",
    "ステーキKING", "しゃぶしゃぶ彩", "お好み焼き大阪", "餃子の館",
]


def make_phone(area_prefix="06"):
    return f"{area_prefix}-{random.randint(1000,9999)}-{random.randint(1000,9999)}"


def make_address(pref, city):
    cho = random.randint(1, 5)
    ban = random.randint(1, 20)
    go  = random.randint(1, 10)
    return f"{pref}{city}{cho}丁目{ban}番{go}号"


def make_url(source, shop_id):
    if source == "tabelog":
        return f"https://tabelog.com/osaka/A2701/A270101/{shop_id}/"
    if source == "hotpepper":
        return f"https://www.hotpepper.jp/A{shop_id}/"
    return f"https://www.google.com/maps/place/{shop_id}"


rows = []
shop_id = 10000

# --- ユニーク店舗 (1000件) ---
base_shops = []
for i in range(1000):
    pref = random.choice(PREFECTURES)
    city = random.choice(CITIES[pref])
    name = random.choice(SHOP_NAMES) + f" {random.choice(['本店','東口店','北店',''])}"
    phone = make_phone(random.choice(["03", "06", "052", "092", "078"]))
    addr  = make_address(pref, city)
    genre = random.choice(GENRES)
    rating = f"{random.uniform(3.0, 4.9):.1f}"
    base_shops.append({
        "name": name, "phone": phone, "address": addr,
        "genre": genre, "rating": rating,
    })
    shop_id += 1

# --- 3ソースに分散（重複あり） ---
for src_idx, source in enumerate(SOURCES):
    sample = random.sample(base_shops, k=700)  # 700件ずつ → 合計2100件・重複多数
    for shop in sample:
        # 表記揺れを加える
        name = shop["name"]
        addr = shop["address"]
        phone = shop["phone"]

        if source == "google":
            # Googleはカタカナ/英語表記になりがち
            phone_disp = phone  # そのまま
        elif source == "tabelog":
            # 食べログは「本店」揺れ
            name = name.replace("本店", "").strip() if random.random() < 0.3 else name
            phone_disp = phone.replace("-", "ー") if random.random() < 0.2 else phone  # 全角ハイフン
        else:
            # ホットペッパーは電話番号が空になることがある
            phone_disp = "" if random.random() < 0.2 else phone
            addr = addr + "　" if random.random() < 0.2 else addr  # 全角スペース混入

        rows.append({
            "name":    name,
            "address": addr,
            "phone":   phone_disp,
            "url":     make_url(source, shop_id),
            "source":  source,
            "genre":   shop["genre"],
            "rating":  shop["rating"] if source == "tabelog" else "",
        })
        shop_id += 1

# シャッフル
random.shuffle(rows)

# 3ファイルに分割して保存
chunk = len(rows) // 3
for i, src in enumerate(SOURCES):
    chunk_rows = rows[i*chunk:(i+1)*chunk]
    path = f"./data/test_{src}.csv"
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["name","address","phone","url","source","genre","rating"])
        writer.writeheader()
        writer.writerows(chunk_rows)
    print(f"生成: {path}  {len(chunk_rows)} 件")

print(f"合計: {len(rows)} 件")
