# Visa Iframe 統合ガイド

## 概要

この統合により、`onboard_card` ツールの呼び出し中にセキュアなカードオンボーディングのために UI に Visa iframe を埋め込むことができます。

## フロー

```
ユーザー → エージェント → onboard_card(use_iframe=True) → iframe 設定を返す → UI が iframe を埋め込む → ユーザーが検証を完了 → トークンがエージェントに送り返される
```

## バックエンド統合

### 1. エージェントツールコール

エージェントが `use_iframe=True` で `onboard_card` を呼び出す場合：

```python
from cart_manager.tools import onboard_card

result = onboard_card(
    card_number="4111111111111111",
    expiration_date="12/25",
    cvv="123",
    card_type="Visa",
    use_iframe=True  # 処理する代わりに iframe 設定を返す
)

# 結果:
{
    "success": True,
    "config": {
        "iframeUrl": "https://sandbox.secure.checkout.visa.com/wallet/v2/wallet.html",
        "apiKey": "YOUR_API_KEY", # pragma: allowlist secret
        "clientAppId": "VICTestAccountTR",
        "locale": "en_US",
        "userEmail": "user@example.com",
        "sessionId": "session_abc123"
    },
    "html": "<iframe src=...>",  # すぐに使用できる HTML
    "message": "Visa iframe でカード検証を完了してください"
}
```

### 2. フロントエンドが設定を受信

チャット UI がこのレスポンスを受信し：
1. レスポンスで `config.iframeUrl` を検出
2. `VisaIframe` コンポーネントをレンダリング
3. トークン完了をリッスン

## フロントエンド統合

### React コンポーネントの使用

```tsx
import { VisaIframe } from './components/VisaIframe';

function ChatInterface() {
  const [iframeConfig, setIframeConfig] = useState(null);

  const handleAgentResponse = (response) => {
    // レスポンスに iframe 設定が含まれているか確認
    if (response.config?.iframeUrl) {
      setIframeConfig(response.config);
    }
  };

  const handleTokenReceived = async (secureToken) => {
    // トークンをエージェントに送り返してオンボーディングを完了
    await fetch('/api/agent/complete-visa-onboarding', {
      method: 'POST',
      body: JSON.stringify({
        sessionId: iframeConfig.sessionId,
        secureToken: secureToken
      })
    });

    setIframeConfig(null); // iframe を閉じる
  };

  return (
    <div>
      {iframeConfig && (
        <VisaIframe
          config={iframeConfig}
          onTokenReceived={handleTokenReceived}
          onError={(err) => console.error(err)}
        />
      )}
      {/* チャット UI */}
    </div>
  );
}
```

### Vanilla JavaScript

```html
<div id="visa-iframe-container"></div>

<script>
function embedVisaIframe(config) {
  const container = document.getElementById('visa-iframe-container');
  const iframe = document.createElement('iframe');

  iframe.src = `${config.iframeUrl}?apiKey=${config.apiKey}&clientAppId=${config.clientAppId}`;
  iframe.style.width = '100%';
  iframe.style.height = '600px';
  iframe.allow = 'payment; publickey-credentials-get';

  container.appendChild(iframe);

  // トークンをリッスン
  window.addEventListener('message', (event) => {
    if (event.data.type === 'SECURE_TOKEN_RECEIVED') {
      completeOnboarding(config.sessionId, event.data.secureToken);
      container.innerHTML = ''; // iframe を削除
    }
  });

  // セッションを初期化
  iframe.onload = () => {
    iframe.contentWindow.postMessage({
      command: 'CREATE_AUTH_SESSION',
      apiKey: config.apiKey,
      clientAppId: config.clientAppId
    }, config.iframeUrl);
  };
}

async function completeOnboarding(sessionId, secureToken) {
  await fetch('/api/agent/complete-visa-onboarding', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sessionId, secureToken })
  });
}
</script>
```

## 完全なバックエンドエンドポイント

トークン受信後にオンボーディングを完了するエンドポイントを追加：

```python
# エージェント API 内
@app.post("/api/agent/complete-visa-onboarding")
async def complete_visa_onboarding(request: Request):
    data = await request.json()
    session_id = data['sessionId']
    secure_token = data['secureToken']

    # セキュアトークンを使用して Visa 登録を完了
    from cart_manager.visa_onboarding import provision_token_with_secure_token

    result = provision_token_with_secure_token(
        secure_token=secure_token,
        email=get_user_email()
    )

    if result['success']:
        # トークンをユーザープロファイルに保存
        save_visa_token_to_profile(result['tokenData'])

    return result
```

## テスト

### 1. バックエンドのテスト
```bash
cd concierge_agent/code
python -c "
from cart_manager.tools import onboard_card
result = onboard_card(
    card_number='4111111111111111',
    expiration_date='12/25',
    cvv='123',
    use_iframe=True
)
print(result)
"
```

### 2. フロントエンドのテスト
ブラウザコンソールを開き、`result['html']` から HTML を貼り付け

## セキュリティノート

- iframe は WebAuthn のために `allow="payment; publickey-credentials-get"` を使用
- すべての通信はオリジン検証付き postMessage 経由
- セキュアトークンは1回限りの使用で、すぐに期限切れ
- CVV や完全なカード番号は決して保存しない

## トラブルシューティング

**iframe が読み込まれない：**
- CORS 設定を確認
- API キーが有効か確認
- HTTPS を確保（Visa で必要）

**postMessage が機能しない：**
- イベントリスナーでオリジンを確認
- iframe の contentWindow がアクセス可能か確認
- メッセージを送信する前に iframe が読み込まれていることを確認

**トークンが受信されない：**
- ブラウザコンソールでエラーを確認
- WebAuthn がサポートされているか確認
- Visa サンドボックス認証情報でテスト
