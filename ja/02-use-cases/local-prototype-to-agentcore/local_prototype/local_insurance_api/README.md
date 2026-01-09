# 保険 API

リアルな サンプルデータを使用した自動車保険 API をシミュレートする FastAPI ベースのアプリケーションです。

## 概要

この API は以下のエンドポイントを提供します：
- 顧客情報の取得
- 車両データと安全評価へのアクセス
- 様々な要因に基づく保険料の計算
- リスク評価の処理
- 利用可能な保険商品の表示
- 保険ポリシーの管理とクエリ

## セットアップ

### 前提条件

- Python 3.10 以上
- pip

### インストール

1. 仮想環境を作成：
   ```bash
   python -m venv venv
   ```

2. 仮想環境を有効化：
   - macOS/Linux の場合：
     ```bash
     source venv/bin/activate
     ```
   - Windows の場合：
     ```bash
     venv\Scripts\activate
     ```

3. 依存関係をインストール：
   ```bash
   pip install -r requirements.txt
   ```

## 使用方法

### API サーバーの起動

```bash
python -m uvicorn server:app --port 8001 --reload
```

API は `http://localhost:8001` で利用可能になります。

### API エンドポイント

| エンドポイント | メソッド | 説明 | サンプルリクエストボディ |
|----------|--------|-------------|---------------------|
| `/` | GET | API 情報のルートエンドポイント | N/A |
| `/health` | GET | ヘルスチェック | N/A |
| `/customer_info` | POST | 顧客情報を取得 | `{"customer_id": "cust-001"}` |
| `/customer_credit` | POST | 顧客の信用情報を取得 | `{"customer_id": "cust-001"}` |
| `/vehicle_info` | POST | 車両情報を取得 | `{"make": "Toyota", "model": "Camry", "year": 2022}` |
| `/risk_factors` | POST | リスク評価を取得 | `{"customer_id": "cust-001", "vehicle_info": {"make": "Toyota", "model": "Camry", "year": 2022}}` |
| `/insurance_products` | POST | フィルタリング、ソート、フォーマットオプション付きで利用可能な保険商品を取得 | `{}`（下記の[保険商品オプション](#保険商品オプション)を参照） |
| `/vehicle_safety` | POST | 車両安全情報を取得 | `{"make": "Toyota", "model": "Camry"}` |
| `/policies` | GET | 全ポリシーを取得 | N/A |
| `/policies` | POST | 様々な条件でポリシーをフィルタリング | `{"status": "active"}`（下記の[ポリシーフィルタリングオプション](#ポリシーフィルタリングオプション)を参照） |
| `/policies/{policy_id}` | GET | ID で特定のポリシーを取得 | N/A |
| `/customer/{customer_id}/policies` | GET | 特定の顧客の全ポリシーを取得 | N/A |
| `/test` | GET | サンプルデータ付きのテストエンドポイント | N/A |

## サンプル curl コマンド

### ルートエンドポイント
```bash
curl http://localhost:8001/
```

### ヘルスチェック
```bash
curl http://localhost:8001/health
```

### 顧客情報の取得
```bash
curl -X POST http://localhost:8001/customer_info \
  -H "Content-Type: application/json" \
  -d '{"customer_id": "cust-001"}'
```

### 車両情報の取得
```bash
curl -X POST http://localhost:8001/vehicle_info \
  -H "Content-Type: application/json" \
  -d '{"make": "Toyota", "model": "Camry", "year": 2022}'
```

### リスク要因の取得
```bash
curl -X POST http://localhost:8001/risk_factors \
  -H "Content-Type: application/json" \
  -d '{"customer_id": "cust-001", "vehicle_info": {"make": "Toyota", "model": "Camry", "year": 2022}}'
```

### 保険商品の取得
```bash
curl -X POST http://localhost:8001/insurance_products \
  -H "Content-Type: application/json" \
  -d '{}'
```

### 全ポリシーの取得
```bash
curl http://localhost:8001/policies
```

### 特定のポリシーを取得
```bash
curl http://localhost:8001/policies/policy-001
```

### 顧客のポリシーを取得
```bash
curl http://localhost:8001/customer/cust-001/policies
```

## ポリシーフィルタリングオプション

`/policies` POST エンドポイントは様々なフィルタリングオプションをサポートしています：

| パラメータ | タイプ | 説明 | 例 |
|-----------|------|-------------|--------|
| `policy_id` | string | 特定のポリシー ID でフィルタリング | `{"policy_id": "policy-001"}` |
| `customer_id` | string | 顧客 ID でフィルタリング | `{"customer_id": "cust-002"}` |
| `status` | string | ステータス（active、expired など）でフィルタリング | `{"status": "active"}` |
| `include_vehicles` | boolean | レスポンスに車両詳細を含める（デフォルト: true） | `{"include_vehicles": false}` |

### ポリシーフィルタークエリの例

```bash
curl -X POST http://localhost:8001/policies \
  -H "Content-Type: application/json" \
  -d '{
    "status": "active",
    "customer_id": "cust-001"
  }'
```

## 保険商品オプション

`/insurance_products` エンドポイントは様々なフィルタリング、ソート、フォーマットオプションをサポートしています：

### フィルタリングオプション

| パラメータ | タイプ | 説明 | 例 |
|-----------|------|-------------|--------|
| `product_id` | string または array | 特定の商品 ID でフィルタリング | `{"product_id": "premium-auto"}` または `{"product_id": ["basic-auto", "standard-auto"]}` |
| `price_range` | object | 価格範囲でフィルタリング | `{"price_range": {"min": 500, "max": 1200}}` |
| `coverage_includes` | array | 特定の補償を含む商品をフィルタリング | `{"coverage_includes": ["collision", "comprehensive"]}` |
| `discount_includes` | array | 特定の割引を提供する商品をフィルタリング | `{"discount_includes": ["loyalty", "good-student"]}` |

### ソートオプション

| パラメータ | タイプ | 説明 | 例 |
|-----------|------|-------------|--------|
| `sort_by` | string | "price"、"name"、"rating" でソート | `{"sort_by": "price"}` |
| `sort_order` | string | "asc" または "desc" 順でソート | `{"sort_order": "desc"}` |

### レスポンスフォーマットオプション

| パラメータ | タイプ | 説明 | 例 |
|-----------|------|-------------|--------|
| `include_details` | boolean | 完全な商品詳細を含める（デフォルト: true） | `{"include_details": false}` |
| `format` | string | レスポンス形式 - "full" または "summary"（デフォルト: "full"） | `{"format": "summary"}` |

### 複雑なクエリの例

```bash
curl -X POST http://localhost:8001/insurance_products \
  -H "Content-Type: application/json" \
  -d '{
    "price_range": {"min": 500, "max": 1200},
    "coverage_includes": ["liability"],
    "sort_by": "price",
    "sort_order": "asc",
    "format": "full"
  }'
```

## データ

API は `data/` ディレクトリにあるサンプルデータを使用しています：

- `customers.json`: 個人情報と運転履歴を含む顧客プロファイル
- `vehicles.json`: 車両仕様と評価
- `credit_reports.json`: 顧客の信用情報
- `products.json`: 保険商品の詳細
- `pricing_rules.json`: 保険料計算のルール
- `policies.json`: サンプル保険ポリシー

## プロジェクト構造
```
insurance_api/
├── app.py                 # FastAPI アプリケーション初期化
├── server.py              # アプリケーション実行のエントリーポイント
├── data_loader.py         # JSON ファイルからデータを読み込み管理するユーティリティ
├── data/                  # サンプルデータファイルを含むディレクトリ
├── requirements.txt       # プロジェクト依存関係
├── routes/                # ドメインごとに整理されたエンドポイントハンドラー
│   ├── __init__.py        # パッケージ初期化
│   ├── customer.py        # 顧客関連のエンドポイント
│   ├── general.py         # ルート、ヘルス、テストエンドポイント
│   ├── insurance.py       # 保険関連のエンドポイント
│   ├── policy.py          # ポリシー関連のエンドポイント
│   └── vehicle.py         # 車両関連のエンドポイント
└── services/              # ドメインごとに整理されたビジネスロジック
    ├── __init__.py        # パッケージ初期化
    ├── data_service.py    # データアクセス関数
    ├── policy_service.py  # ポリシー管理関数
    ├── product_service.py # 保険商品ビジネスロジック
    └── utils.py           # ユーティリティ関数
```

### 主要コンポーネント

- **app.py**: ミドルウェアとルーター登録を含む FastAPI アプリケーションを作成・設定
- **server.py**: アプリケーションを実行するシンプルなエントリーポイント
- **routes/**: ドメイン（顧客、車両、保険、ポリシー）ごとに整理されたエンドポイントハンドラーを含む
- **services/**: ビジネスロジックとデータアクセス関数を含む
- **data_loader.py**: JSON ファイルからサンプルデータを読み込みアクセスを提供
