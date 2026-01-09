# Visa ローカルバックエンドサーバー

Visa カードオンボーディングと決済統合のためのローカル開発サーバーです。

## クイックスタート

### 前提条件

1. **Python 3.11+** と `uv` パッケージマネージャー
2. Secrets Manager の Visa シークレットにアクセスできる **AWS 認証情報**
3. Visa iframe CSP 用の **hosts ファイルエントリ**（以下参照）

### セットアップ

**2 つのターミナルが必要で、両方とも AWS アカウントにサインインしている必要があります：**

- **ターミナル 1**: Web UI を実行（`npm run dev`）し、`https://vcas.local.com:9000` を開く
- **ターミナル 2**: 以下の手順に従って Visa バックエンドサーバーを実行し、`http://localhost:5001` を開く

#### ターミナル 2 - Visa バックエンドサーバーセットアップ

1. **hosts エントリを追加**（初回設定）：
   ```bash
   sudo sh -c 'echo "127.0.0.1 vcas.local.com" >> /etc/hosts'
   ```
   これは Visa の iframe CSP がホワイトリストに登録されたドメインのみを許可するため必要です。

2. このディレクトリに移動
    ```
    cd local-visa-server
    ```

3. 仮想環境を作成して依存関係をインストール
    ```
    uv venv
    source .venv/bin/activate
    uv pip install -r requirements.txt
    ```

4. Visa iframe 用の hosts エントリを追加（初回設定）
    これは Visa の iframe CSP が特定のドメインのみを許可するため必要です
    ```
    ../scripts/setup-visa-local.sh
    ```

5. サーバーを実行
    ```
    python server.py
    ```

6. localhost にアクセス

### hosts ファイルエントリが必要な理由

Visa の iframe は特定のドメインのみを許可する Content Security Policy（CSP）ヘッダーを送信します：
```
frame-ancestors 'self' https://vcas.local.com:9000 ...
```

これはブラウザで強制されるセキュリティです - UI がホワイトリストに登録されたドメインにない場合、iframe はロードを拒否します。`vcas.local.com` はサンドボックス開発用の Visa の事前登録済みテストドメインです。

**これが必要なのは UI のみです** - バックエンドサーバーは `localhost:5001` のままで問題ありません。

## サーバーエンドポイント

| エンドポイント | メソッド | 説明 |
|---------------|----------|------|
| `/` | GET | ヘルスチェック |
| `/api/visa/secure-token` | GET | Visa OAuth トークンを取得 |
| `/api/visa/onboard-card` | POST | カード登録 + トークンプロビジョニング |
| `/api/visa/device-attestation` | POST | WebAuthn アテステーション |
| `/api/visa/device-binding` | POST | デバイスをトークンにバインド |
| `/api/visa/step-up` | POST | OTP 方式を選択 |
| `/api/visa/validate-otp` | POST | OTP コードを検証 |
| `/api/visa/complete-passkey` | POST | パスキー登録を完了 |
| `/api/visa/vic/enroll-card` | POST | VIC 登録 |
| `/api/visa/vic/initiate-purchase` | POST | 購入を開始 |
| `/api/visa/vic/payment-credentials` | POST | 決済クリプトグラムを取得 |


## ファイル構造

```
local-visa-server/
├── server.py              # メイン Flask サーバーエントリーポイント
├── requirements.txt       # Python 依存関係
├── README.md              # このファイル
├── visa/                  # Visa API 統合
│   ├── __init__.py
│   ├── flow.py            # Visa フローオーケストレーション
│   ├── api_wrapper.py     # 簡略化されたラッパー関数
│   ├── secure_token.py    # 直接セキュアトークン API
│   └── helpers.py         # ユーティリティ関数
└── config/                # 設定ファイル
    └── .gitkeep
```

## セキュリティに関する注意事項

- カードデータはこのサーバーに触れません - iframe から Visa に直接送信されます
- すべての Visa 認証情報は AWS Secrets Manager に保存されます
- CORS は既知のオリジンのみに制限されています
- 機密トークンはログに記録されません
