# UBS Evidence Lab - Fund Manager Data Dashboard

ファンドマネージャー向けの UBS Evidence Lab API データ確認ダッシュボード

---

## 概要

Streamlit ベースのモジュラーダッシュボードアプリケーションです。
UBS Evidence Lab の各種 API からデータを取得し、インタラクティブに分析・可視化できます。

**モジュラー設計**により、新しい UBS API サブアプリを簡単に追加できます。

### 現在のモジュール

| モジュール | 説明 | データソース |
|-----------|------|------------|
| 🏦 **Central Bank Sentiment** | 主要中央銀行（BOJ, FED, ECB）の政策スタンス・センチメント分析 | dataAssetKey: 10487 |
| 📈 **Nowcasting** | 米国主要経済指標のリアルタイム予測と実績値比較 | dataAssetKey: 10441 |
| 💼 **Job Listings Monitor** | 米国求人掲載データによる雇用動向モニタリング | dataAssetKey: 10224 |

---

## クイックスタート

### 1. 環境設定

```bash
pip install -r requirements.txt
```

### 2. APIキーの設定

`API key.txt` に UBS Evidence Lab API トークンを保存

### 3. 起動

```bash
streamlit run app.py
```

ブラウザが自動で開きます（通常 http://localhost:8501）

---

## ファイル構成

```
UBS/
├── app.py                              # メインエントリポイント（ホーム画面・ナビゲーション）
├── requirements.txt                    # 依存パッケージ
├── API key.txt                         # APIトークン
├── start.bat                           # Windows起動スクリプト
│
├── config/                             # 共通設定
│   └── settings.py                     # プロキシ、トークン、定数
│
├── core/                               # 共通基盤
│   ├── api_client.py                   # UBS Evidence Lab API クライアント
│   └── ui_components.py               # 共通UIコンポーネント（CSS, カード, エクスポート）
│
├── modules/                            # サブアプリ群
│   ├── registry.py                     # モジュール登録・管理
│   ├── sentiment/                      # 中央銀行センチメント
│   │   ├── data.py                     #   データ取得・処理
│   │   └── dashboard.py               #   ダッシュボードUI
│   ├── nowcasting/                     # 経済指標ナウキャスティング
│   │   ├── data.py
│   │   └── dashboard.py
│   └── job_listings/                   # 求人掲載モニター
│       ├── data.py
│       └── dashboard.py
│
└── docs/                               # ドキュメント
    ├── api_reference.txt               # Evidence Lab API 仕様書
    ├── sentiment_api.txt               # センチメント API スキーマ
    ├── nowcasting_api.txt              # ナウキャスティング API スキーマ
    ├── methodology.txt                 # 分析メソドロジー
    └── dataset_catalog.txt             # 全データセットカタログ
```

---

## 新しいサブアプリの追加方法

モジュラー設計により、3ステップで新しい UBS API サブアプリを追加できます。

### Step 1: モジュールディレクトリを作成

```
modules/new_module/
├── __init__.py
├── data.py          # データ取得・処理ロジック
└── dashboard.py     # show_dashboard() 関数を実装
```

### Step 2: data.py と dashboard.py を実装

```python
# modules/new_module/data.py
ENDPOINT = "framework-name/view/v2/data?dataAssetKey=XXXXX"

def fetch_data(client, start_date_str, end_date_str):
    filters = {
        "filters": [
            {"filterType": ">=", "field": "periodEndDate", "value": start_date_str},
            {"filterType": "<=", "field": "periodEndDate", "value": end_date_str}
        ]
    }
    return client.fetch_paginated(ENDPOINT, filters)
```

```python
# modules/new_module/dashboard.py
from core.api_client import UBSAPIClient
from core.ui_components import apply_common_css, render_sidebar_header

def show_dashboard():
    apply_common_css()
    st.title("New Module Dashboard")
    # ... ダッシュボードの実装
```

### Step 3: レジストリに登録

`modules/registry.py` の `MODULES` リストに追加:

```python
{
    "id": "new_module",
    "name": "New Module Name",
    "icon": "🔬",
    "description": "モジュールの説明",
    "import_path": "modules.new_module.dashboard",
    "function": "show_dashboard",
},
```

ホーム画面とナビゲーションに自動的に反映されます。

---

## モジュール詳細

### 🏦 Central Bank Sentiment Tracker

UBS AI LLMs を活用して中央銀行スピーカーの演説を分析し、金融政策スタンスを追跡。

**対象:** BOJ（日本銀行）, FED（連邦準備制度）, ECB（欧州中央銀行）

| タブ | 内容 |
|-----|------|
| Overview | 中央銀行別センチメント推移の一覧比較（Smoothed/Unsmoothed） |
| Topic Analysis | トピック別（インフレ、雇用等）寄与度分析 |
| Speaker Analysis | 発言者別センチメント分析・ヒートマップ |
| Data Export | CSV/Excel/JSON エクスポート |

**センチメントスコア:** -1.0（ハト派/緩和的） 〜 +1.0（タカ派/引締め的）

### 📈 Nowcasting

非伝統的ビッグデータを活用した経済指標の予測。公式発表より数週間早い推計を提供。

**対象指標:** ISM Manufacturing, Auto SAAR, Nonfarm Payrolls, CPI, Core CPI, Private Construction Spending, Industrial Production

| タブ | 内容 |
|-----|------|
| チャート分析 | 予測値 vs 実績値の比較チャート |
| 統計情報 | 指標別の精度統計 |
| CPI寄与度 | CPI構成要素の寄与度分解（積み上げ棒グラフ + 折れ線） |
| データ出力 | 全データの一括エクスポート |

### 💼 Job Listings Monitor

約50,000社の企業キャリアサイトから直接取得した求人掲載データで雇用動向をモニタリング。

**データ:** 2016年〜、週次更新、BLS JOLTS 分類準拠

| タブ | 内容 |
|-----|------|
| セクター概要 | セクター別求人掲載動向の概観 |
| 時系列分析 | セクター別の求人数推移 |
| 地域・職種 | 地域別・職種別の分析 |
| データ出力 | CSV/Excel/JSON エクスポート |

**利用可能ビュー:** Time Series (v3), Regional Analysis (v2), Job Family (v2)

---

## 技術仕様

- **フレームワーク:** Streamlit
- **可視化:** Plotly（インタラクティブチャート）
- **API:** UBS Evidence Lab API v2（JWT Bearer認証）
- **データ処理:** Pandas, NumPy
- **エクスポート:** CSV, Excel (openpyxl), JSON

### 依存パッケージ

```
streamlit, pandas, requests, plotly, openpyxl, urllib3, numpy
```

---

## トラブルシューティング

| 問題 | 対処法 |
|------|--------|
| データが取得できない | ネットワーク接続確認、`API key.txt` のトークン確認、`neo.ubs.com` への接続確認 |
| グラフが表示されない | データ取得済みか確認、フィルター条件を緩める |
| Excel出力エラー | `pip install openpyxl` を実行 |
| プロキシ関連エラー | `config/settings.py` のプロキシ設定を環境に合わせて変更 |

---

## 変更履歴

### v5.0 (2026-03)
- **モジュラーアーキテクチャへ移行**: フラットな2ファイル構成 → パッケージ構造
- **共通API クライアント**: 認証・リトライ・ページネーションを統一 (`core/api_client.py`)
- **共通UIコンポーネント**: CSS・カード・エクスポートを共通化 (`core/ui_components.py`)
- **モジュールレジストリ**: 新規サブアプリ追加を3ステップで完了 (`modules/registry.py`)
- **Job Listings Monitor 追加**: 米国求人掲載データ分析サブアプリを新規実装
- **ファイル命名の改善**: 役割が明確なディレクトリ・ファイル名

### v4.0 (2025-12)
- メソドロジー日本語化、グラフサイズ改善、UI統一

### v3.0 (2025-12)
- タブ統合（7→5）、各タブ独立フィルター化

### v2.0 (2025-12)
- 12タブ構成、プロキシ切り替え対応

---

## ライセンス

このアプリケーションは UBS Evidence Lab API を使用しています。データの使用には適切なライセンスが必要です。
