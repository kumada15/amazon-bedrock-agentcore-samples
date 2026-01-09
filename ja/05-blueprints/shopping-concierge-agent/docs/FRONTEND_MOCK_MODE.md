# フロントエンドモックモード - Visa バックエンド不要！

## 概要

**Visa API 認証情報やローカル Visa サーバーなしで** **「支払い方法を追加」** ボタンを使用できます！フロントエンドはブラウザで直接モック Visa API レスポンスを使用でき、Visa 統合のセットアップなしで決済フローをテストできます。

## クイックスタート（デフォルト）

### 1. フロントエンドモックモードを有効化

`web-ui/.env.local` を編集：

```bash
VITE_VISA_MOCK_MODE=true
```

**これがデフォルト設定です** - モックモードはデフォルトで有効になっています！

### 2. アプリケーションを起動

```bash
# プロジェクトルートから
npm run dev
```

これで完了です！Visa サーバーや認証情報は不要です。

### 3. 「支払い方法を追加」をテスト

1. `https://vcas.local.com:9000` を開く
2. サインインまたは新しいユーザーを作成
3. ショッピングエージェントを使用してカートにアイテムを追加
4. **「チェックアウト」** または **「支払い方法を追加」** をクリック
5. 任意のテストカード詳細を入力
6. フローを完了（すべてのステップはブラウザでモックされます！）


## 比較

| モード | Visa サーバー？ | セットアップ | 速度 |
|------|-------------|-------|-------|
| **フロントエンドモック**（デフォルト） | ❌ 不要 | ✅ 環境変数を設定するだけ | ⚡ 即時 |
| **実際の Visa API** | ✅ 必要 | 認証情報 + シークレット | 🐌 実際の API コール |

## 設定オプション

### オプション 1：フロントエンドモックモード（開発に推奨）

```bash
# web-ui/.env.local
VITE_VISA_MOCK_MODE=true
```

**メリット：**
- ✅ バックエンドサーバー不要
- ✅ Python セットアップ不要
- ✅ 即時レスポンス
- ✅ 認証情報不要
- ✅ フロントエンド開発に最適

**デメリット：**
- ⚠️ バックエンド統合をテストできない
- ⚠️ 実際の Visa API フローをテストできない

### オプション 2：ローカル Visa サーバー（モックモード）

```bash
# web-ui/.env.local
VITE_VISA_MOCK_MODE=false
VISA_INTEGRATION_ENABLED=true

# ターミナル 1: ローカル Visa サーバーを起動（リアルモード）
cd concierge_agent/local-visa-server
export VISA_INTEGRATION_ENABLED=true
python3 server.py

# ターミナル 2: アプリケーションを起動
cd ../..
npm run dev
```

**メリット：**
- ✅ 実際の Visa 統合をテスト
- ✅ 実際のカードトークン化
- ✅ 実際の OTP と生体認証

**デメリット：**
- ⚠️ Visa API 認証情報が必要
- ⚠️ `infrastructure/certs/` に Visa 証明書が必要
- ⚠️ 最も遅いオプション
- ⚠️ API コストが発生する可能性

**注意：** 詳細なセットアップ手順については [VISA_LOCAL_SETUP.md](./VISA_LOCAL_SETUP.md) を参照してください。

### 問題：「fetch failed」エラーが発生

おそらく `VITE_VISA_MOCK_MODE=false` ですが、ローカル Visa サーバーが実行されていません。

**修正：** 以下のいずれかを実行：
1. フロントエンドモックを有効化：`VITE_VISA_MOCK_MODE=true`
2. またはローカル Visa サーバーを起動：`cd concierge_agent/local-visa-server && python3 server.py`

### 問題：フルスタック統合をテストしたい

**false に設定：**
```bash
VITE_VISA_MOCK_MODE=false
```

**ローカル Visa サーバーを起動：**
```bash
cd concierge_agent/local-visa-server
python3 server.py
```

**アプリケーションを起動：**
```bash
cd ../..
npm run dev
```

## 作成されたファイル

### 新しいフロントエンドモックサービス
- **`web-ui/src/services/visaMockService.ts`** - モック Visa API サービス
  - すべてのモックレスポンスを提供
  - ネットワーク遅延をシミュレート
  - 予測可能なテストデータを返す

### 更新されたコンポーネント
- **`web-ui/src/components/VisaIframeAuth.tsx`** - モックサービスを使用するよう更新
  - `VITE_VISA_MOCK_MODE` 環境変数をチェック
  - 設定に基づいてモックまたはバックエンドにルーティング
  - 現在のモードをコンソールにログ

### 設定
- **`web-ui/.env.local`** - `VITE_VISA_MOCK_MODE=true` を追加
- **`web-ui/.env.local.example`** - すべてのオプションをドキュメント化したテンプレート

## 関連ドキュメント

- [VISA_LOCAL_SETUP.md](./VISA_LOCAL_SETUP.md) - 実際の API でローカル Visa サーバーをセットアップ
- [VISA_FEATURE_FLAG.md](./VISA_FEATURE_FLAG.md) - 完全な機能フラグシステム
- [VISA_IFRAME_INTEGRATION.md](./VISA_IFRAME_INTEGRATION.md) - Visa iframe 統合の詳細
