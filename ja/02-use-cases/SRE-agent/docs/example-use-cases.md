# ユースケースの例

## Pod 障害の調査

```bash
sre-agent --prompt "Our database pods are crash looping in production"
```

エージェントは協力して Pod のステータスを確認し、イベントを分析し、メモリ使用量のトレンドを調査し、修復手順を提供します。

## パフォーマンスの問題の診断

```bash
sre-agent --prompt "API response times have degraded 3x in the last hour"
```

システムは複数のディメンションにわたるメトリクスを相関させて、レイテンシの原因と設定の問題を特定します。

## インタラクティブなトラブルシューティングセッション

```bash
sre-agent --interactive

👤 You: We're seeing intermittent 502 errors from the payment service
🤖 Multi-Agent System: Investigating intermittent 502 errors...

👤 You: What's causing the queue buildup?
🤖 Multi-Agent System: Analyzing payment queue patterns...
```

インタラクティブモードでは、複雑な調査のためのマルチターン会話が可能です。

## プロアクティブな監視

```bash
# 朝のヘルスチェック
sre-agent --prompt "Perform a comprehensive health check of all production services"

# キャパシティプランニング
sre-agent --prompt "Analyze resource utilization trends and predict when we'll need to scale"

# セキュリティ監査
sre-agent --prompt "Check for any suspicious patterns in authentication logs"
```

プロアクティブな監視とヘルスチェッククエリの例です。
