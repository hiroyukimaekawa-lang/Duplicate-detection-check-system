# Deduplicator Pro: レストランデータ重複検出・名寄せシステム

Deduplicator Proは、複数のデータソースから収集されたレストラン情報を統合し、高度なファジーロジックを用いて重複を排除するためのWebアプリケーションです。

![Main Dashboard](public/favicon.ico) <!-- もし実際のスクリーンショットがあれば差し替えてください -->

## 🚀 主な機能

- **高度な重複検知**: `rapidfuzz` を用いた曖昧一致判定により、店名や住所の表記ゆれを考慮した名寄せを実現。
- **マルチソース統合**: Google Maps、食べログ、ホットペッパー、ぐるなび等、異なるフォーマットのCSVを同一の基準で処理。
- **インテリジェント・フィルタリング**:
  - **チェーン店除外**: 特定のキーワードに基づきチェーン店を自動判別し、重複リストや除外リストへ移動。
  - **商業施設フィルタ**: モールやビル自体のレコードを検知し、リストをクリーンに保ちます。
- **プライバシー保護**: 電話番号や住所の特定部分をマスクする「個人情報保護モード」を搭載。
- **AIフィードバックループ**: システムの判定結果に対してユーザーがフィードバック（正誤判定）を行うことで、検知精度を継続的に向上。
- **リッチなエクスポート**: 処理結果を統計情報付きのExcel（マルチタブ）またはCSV形式でダウンロード可能。

## 🛠 テクノロジースタック

### Frontend
- **Framework**: [Next.js 16 (App Router)](https://nextjs.org/)
- **Language**: TypeScript
- **Styling**: Vanilla CSS (Glassmorphism design)

### Backend
- **Framework**: [FastAPI](https://fastapi.tiangolo.com/)
- **Language**: Python 3.9+
- **Key Libraries**: 
  - `pandas`: データ処理
  - `rapidfuzz`: 高速ファジー文字列照合
  - `openpyxl`: Excel出力処理
  - `slowapi`: レート制限 (Security)

## 📦 セットアップ

### 1. リポジトリのクローン
```bash
git clone https://github.com/hiroyukimaekawa-lang/Duplicate-detection-check-system.git
cd Duplicate-detection-check-system
```

### 2. バックエンドの設定
```bash
# 仮想環境の作成
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 依存関係のインストール
pip install -r requirements.txt

# APIの起動
uvicorn api.index:app --reload --port 8000
```

### 3. フロントエンドの設定
```bash
# 依存関係のインストール
npm install

# 開発サーバーの起動
npm run dev
```

ブラウザで `http://localhost:3000` にアクセスしてください。

## 📖 使い方

1. **アップロード**: 重複チェックを行いたいCSVファイルを選択またはドラッグ＆ドロップします。
2. **オプション選択**: 重複判定の基準（店名、電話番号、住所）や、チェーン店除外の有無を設定します。
3. **実行**: 「重複排除を実行」ボタンをクリック。
4. **レビュー**: AIによる判定結果を確認し、必要に応じて「正しい/間違い」のフィードバックを行います。
5. **ダウンロード**: クリーンになった統合リストをExcelまたはCSVで取得します。

## 🛡 ライセンス

&copy; 2026 重複検出チェックシステム。All rights reserved.
