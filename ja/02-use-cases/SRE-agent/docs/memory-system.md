# SRE エージェントメモリシステム

## 概要

SRE エージェントには、[Amazon Bedrock AgentCore Memory](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory.html) を基盤とした高度な長期メモリシステムが含まれており、永続的なユーザー好み、クロスセッション学習、パーソナライズされた調査体験を可能にします。このシステムはユーザーの好みを記憶し、過去の調査から学習し、個々のユーザーの役割とワークフローに基づいてレポートをカスタマイズします。

システムは異なるタイプの情報に対して 3 つの異なるメモリ戦略を提供し、パーソナライズされた調査をデモンストレーションするためのユーザーペルソナが事前設定されています。

## 事前設定されたユーザーペルソナ

システムには [`scripts/user_config.yaml`](../scripts/user_config.yaml) に 2 つのサンプルユーザーペルソナが付属しており、パーソナライズされた調査がどのように機能するかを示しています：

### Alice - テクニカル SRE エンジニア
- **調査スタイル**: 包括的な分析を伴う詳細で体系的な多次元調査
- **コミュニケーション**: 詳細なメトリクスとトラブルシューティング手順を含む技術チームチャネル（`#alice-alerts`、`#sre-team`）
- **エスカレーション**: 15 分遅延しきい値でテクニカルマネジメント（`alice.manager@company.com`）
- **レポート**: ステップバイステップの手法と完全なツール参照を含む技術的な解説
- **好み**: 詳細な分析、UTC タイムゾーン、トラブルシューティング手順を含む

### Carol - エグゼクティブ/ディレクター
- **調査スタイル**: ビジネスインパクト分析と簡潔なプレゼンテーションに焦点を当てたエグゼクティブ向け
- **コミュニケーション**: フィルタリングされた通知（クリティカルのみ）を含む戦略的チャネル（`#carol-executive`、`#strategic-alerts`）
- **エスカレーション**: より速い 20 分タイムラインでエグゼクティブチーム（`carol.director@company.com`）
- **レポート**: 詳細な技術的手順なしのビジネス重視のサマリー、インパクトとビジネス結果を強調
- **好み**: エグゼクティブサマリー形式、EST タイムゾーン、ビジネスインパクト重視

## パーソナライズされた調査の例

異なるユーザー ID で調査を実行すると、エージェントは同様の技術的発見を生成しますが、各ユーザーの好みに応じて提示します：

```bash
# Alice の詳細な技術調査
USER_ID=Alice sre-agent --prompt "API response times have degraded 3x in the last hour" --provider bedrock

# Carol のエグゼクティブ重視の調査
USER_ID=Carol sre-agent --prompt "API response times have degraded 3x in the last hour" --provider bedrock
```

両方のコマンドは同じ技術的問題を特定しますが、異なる方法で提示します：
- **Alice** はステップバイステップのトラブルシューティングと包括的なツール参照を含む詳細な技術分析を受け取ります
- **Carol** は迅速なエスカレーションタイムラインを含むビジネスインパクトに焦点を当てたエグゼクティブサマリーを受け取ります

メモリシステムが同一のインシデントをどのようにパーソナライズするかの詳細な比較については、以下を参照してください：[**メモリシステムレポート比較**](examples/Memory_System_Analysis_User_Personalization_20250802_162648.md)

## Amazon Bedrock AgentCore Memory アーキテクチャ

メモリシステムは、自動 namespace ルーティングを備えた Amazon Bedrock AgentCore Memory の高度なイベントベースモデルを使用します：

### メモリ戦略と Namespace
SRE エージェントが初期化されると、特定の namespace パターンを持つ 3 つのメモリ戦略が作成されます：

1. **ユーザー好み戦略**: Namespace パターン `/sre/users/{user_id}/preferences`
2. **インフラストラクチャ知識戦略**: Namespace パターン `/sre/infrastructure/{user_id}/{session_id}`
3. **調査メモリ戦略**: Namespace パターン `/sre/investigations/{user_id}/{session_id}`

### Namespace ルーティングの仕組み
重要な洞察は、**SRE エージェントは `create_event()` を呼び出す際に actor_id を提供するだけでよい**ということです。Amazon Bedrock AgentCore Memory は自動的に：

1. **戦略マッチング**: メモリリソースに関連付けられたすべての戦略を調査
2. **Namespace 解決**: actor_id に基づいてイベントが属する namespace を決定
3. **自動ルーティング**: 明示的な namespace 指定なしで正しい戦略の namespace にイベントを配置
4. **複数戦略ストレージ**: namespace が一致する場合、単一のイベントを複数の戦略に保存可能

### メモリ Namespace 分離のための Actor ID 設計
メモリシステムは適切な namespace 分離を確保するために一貫した actor_id 戦略を使用します：

- **ユーザー好み**: 個人 namespace 用に user_id を actor_id として使用（例："Alice"）（`/sre/users/Alice/preferences`）
- **インフラストラクチャ知識**: ドメイン専門知識 namespace 用にエージェント固有の actor_id を使用（例："kubernetes-agent"）
- **調査サマリー**: 個人調査履歴用に user_id を actor_id として使用（`/sre/investigations/Alice`）
- **会話メモリ**: 個人会話コンテキストを維持するために user_id を使用

この設計により以下が保証されます：
- ユーザー固有のデータは個々のユーザーに分離されたまま
- インフラストラクチャ知識はそれを発見したエージェントによって整理
- メモリ操作は正しい namespace に自動的にルーティング
- クロスセッションメモリ取得が確実に動作

### イベントベースモデルの利点
- **不変イベント**: すべてのメモリエントリは変更できない不変イベントとして保存
- **累積学習**: 新しいイベントは古いものを削除せずに時間とともに蓄積
- **戦略集約**: メモリ戦略は namespace からイベントを集約して関連コンテキストを提供
- **自動整理**: イベントはユーザー、セッション、メモリタイプによって自動的に整理

### イベントフローの例
```python
# SRE エージェントは actor_id とコンテンツだけで create_event を呼び出す
memory_client.create_event(
    memory_id="sre_agent_memory-xyz",
    actor_id="Alice",  # Amazon Bedrock AgentCore Memory はこれを使用して正しい namespace にルーティング
    session_id="investigation_2025_01_15",
    messages=[("preference_data", "ASSISTANT")]
)

# Amazon Bedrock AgentCore Memory は自動的に：
# 1. このメモリのすべての戦略 namespace をチェック
# 2. actor_id "Alice" を namespace "/sre/users/Alice/preferences" にマッチ
# 3. ユーザー好み戦略にイベントを保存
# 4. 将来の取得でイベントを利用可能に
```

## メモリ戦略

以下は Amazon Bedrock AgentCore がサポートする 3 つの長期メモリ戦略です（[メモリ入門ガイド](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-getting-started.html)を参照）：

### 1. ユーザー好みメモリ
**戦略:** 90 日保持のセマンティックメモリ
**目的:** ユーザー固有の運用好みを記憶

**キャプチャ内容:**
- エスカレーション連絡先と手順
- 通知チャネル（Slack、メールなど）
- 調査ワークフローの好み
- コミュニケーションスタイルの好み

**使用例:**
```python
# ユーザーが "データベースの問題は ops-team@company.com にエスカレート" と言及した場合
# システムは自動的にキャプチャ：
{
  "user_id": "user123",
  "preference_type": "escalation",
  "preference_value": {
    "contact": "ops-team@company.com",
    "service_category": "database"
  },
  "context": "Redis 接続障害の調査"
}
```

### 2. インフラストラクチャ知識メモリ
**戦略:** 30 日保持のセマンティックメモリ
**目的:** インフラストラクチャパターンと関係の理解を構築

**キャプチャ内容:**
- サービスの依存関係と関係
- 障害パターンと一般的な問題
- 設定インサイトとベストプラクティス
- パフォーマンスベースラインとしきい値

**使用例:**
```python
# サービス停止を調査する際、システムは学習：
{
  "service_name": "web-api",
  "knowledge_type": "dependency",
  "knowledge_data": {
    "depends_on": "postgres-db",
    "failure_mode": "connection_timeout",
    "typical_recovery_time": "2-5 minutes"
  },
  "confidence": 0.8
}
```

### 3. 調査サマリーメモリ
**戦略:** 60 日保持のサマリーメモリ
**目的:** 学習と参照のための調査履歴を維持

**キャプチャ内容:**
- 調査タイムラインと実行されたアクション
- 主要な発見と根本原因
- 解決戦略と結果
- チーム間コラボレーションコンテキスト

**使用例:**
```python
{
  "incident_id": "incident_20250128_1045",
  "query": "Why is the checkout service responding slowly?",
  "timeline": [
    {"time": "10:45", "action": "メトリクスエージェントで調査開始"},
    {"time": "10:47", "action": "高い CPU 使用率を特定"},
    {"time": "10:50", "action": "エラーのアプリケーションログを確認"}
  ],
  "actions_taken": [
    "CPU とメモリメトリクスを分析",
    "アプリケーションエラーログをレビュー",
    "支払い処理でメモリリークを特定"
  ],
  "resolution_status": "completed",
  "key_findings": [
    "支払いサービスのメモリリークが 2GB/時間を消費",
    "ピークトラフィック時にデータベース接続プールが枯渇",
    "サーキットブレーカーの欠如がカスケード障害を引き起こす"
  ]
}
```

## 調査中のメモリフロー

```
┌─────────────┐    ┌─────────────────────┐              ┌──────────────────────┐
│    ユーザー   │    │     Supervisor      │              │  Amazon Bedrock      │
│             │    │      Agent          │              │  AgentCore Memory    │
└──────┬──────┘    └──────────┬──────────┘              └──────────┬───────────┘
       │                      │                                    │
       │ 調査クエリ            │                                    │
       ├─────────────────────►│                                    │
       │                      │                                    │
       │              ┌───────▼───────┐                            │
       │              │ on_investigation_start()                   │
       │              │ (memory_hooks) │                           │
       │              └───────┬───────┘                            │
       │                      │                                    │
       │                      │ retrieve_memory(preferences)       │
       │                      ├───────────────────────────────────►│
       │                      │◄───────────────────────────────────┤
       │                      │ ユーザー好み (10)                    │
       │                      │                                    │
       │                      │ retrieve_memory(infrastructure)    │
       │                      ├───────────────────────────────────►│
       │                      │◄───────────────────────────────────┤
       │                      │ インフラストラクチャデータ (50)        │
       │                      │                                    │
       │                      │ retrieve_memory(investigations)    │
       │                      ├───────────────────────────────────►│
       │                      │◄───────────────────────────────────┤
       │                      │ 過去の調査 (5)                       │
       │                      │                                    │
       │              ┌───────▼───────┐                            │
       │              │ メモリツール付きプランニングエージェント      │
       │              │ (supervisor.py)                            │
       │              └───────┬───────┘                            │
       │                      │                                    │
       │              ┌───────▼───────┐                            │
       │              │ 調査実行                                    │
       │              └───────┬───────┘                            │
       │                      │                                    │
       │                      ├─► メトリクスエージェント              │
       │                      ├─► ログエージェント                   │
       │                      ├─► K8s エージェント                   │
       │                      ├─► ランブックエージェント              │
       │                      │                                    │
       │              ┌───────▼───────┐                            │
       │              │ エージェントレスポンス処理                    │
       │              │ (パターン抽出 & ストレージ)                  │
       │              └───────┬───────┘                            │
       │                      │                                    │
       │              ┌───────▼───────┐                            │
       │              │ on_investigation_complete()                │
       │              │ (調査サマリー保存)                          │
       │              └───────┬───────┘                            │
       │                      │                                    │
       │ 最終レスポンス         │                                    │
       │◄─────────────────────┤                                    │
       │                      │                                    │
```

### 主要なメモリインタラクション

メモリシステムは調査中の 3 つの重要なポイントで統合されます。[`supervisor.py`](../sre_agent/supervisor.py) は起動時にメモリ取得をオーケストレーションし、完了時に調査サマリーを保存します。個々のエージェントレスポンスは [`agent_nodes.py`](../sre_agent/agent_nodes.py) によって処理され、[`memory/hooks.py`](../sre_agent/memory/hooks.py) を通じてパターン抽出をトリガーします。

- **調査開始**: コンテキストを提供するためにユーザー好み、インフラストラクチャ知識、過去の調査を取得
- **エージェントレスポンス**: エスカレーション連絡先、通知チャネル、サービス依存関係などのパターンを自動的に抽出
- **調査完了**: タイムライン、実行されたアクション、主要な発見を含む包括的なサマリーを保存

## メモリツールアーキテクチャとプランニング統合

メモリシステムは **supervisor エージェントのみがメモリツールに直接アクセスできる** 集中型アーキテクチャを使用します：

### ツール分配アーキテクチャ
- **Supervisor エージェント**: 4 つすべてのメモリツール（`retrieve_memory`、`save_preference`、`save_infrastructure`、`save_investigation`）にアクセス
- **個別エージェント**: メモリツールへの直接アクセスなし、ドメイン固有ツールのみ：
  - **Kubernetes エージェント**: 5 つの k8s-api ツール（get_pod_status、get_deployment_status など）
  - **アプリケーションログエージェント**: 5 つの logs-api ツール（search_logs、get_error_logs など）
  - **パフォーマンスメトリクスエージェント**: 5 つの metrics-api ツール（get_performance_metrics、analyze_trends など）
  - **運用ランブックエージェント**: 5 つの runbooks-api ツール（search_runbooks、get_incident_playbook など）

### 集中型メモリ管理
この設計により以下が保証されます：
- **メモリ操作は supervisor を通じて調整**
- **個別エージェントはメモリの複雑さなしにドメイン専門知識に集中**
- **メモリコンテキストは一度取得され、必要に応じてエージェントに配布**
- **すべての調査で一貫したメモリパターン**

### 利用可能なメモリツール（Supervisor のみ）
- **save_preference**: ユーザー好みを長期メモリに保存
- **save_infrastructure**: インフラストラクチャ知識を長期メモリに保存
- **save_investigation**: 調査サマリーを長期メモリに保存
- **retrieve_memory**: 長期メモリから関連情報を取得

### プランニングにおけるメモリコンテキスト

調査計画を作成する際、supervisor エージェントは 3 つのソースからメモリコンテキストを組み込みます。プランニングエージェントは `retrieve_memory` ツールを使用して計画を作成する前に関連コンテキストを収集します。

#### プランニングエージェントのメモリ使用例

以下は `agent.log` からの実例で、プランニングエージェントがメモリコンテキストをどのように取得して使用するかを示しています：

```log
# プランニング中のメモリコンテキスト取得（agent.log より）
2025-08-03 17:48:56,072,p1290668,{supervisor.py:339},INFO,Retrieved memory context for planning: 10 preferences, 50 knowledge items from 1 agents, 5 past investigations

# コンテキスト収集のためのプランニングエージェントツール呼び出し
2025-08-03 17:49:01,067,p1290668,{tools.py:317},INFO,retrieve_memory called: type=preference, query='user settings communication escalation notification', actor_id=Alice -> Alice, max_results=5
2025-08-03 17:49:01,067,p1290668,{client.py:236},INFO,Retrieving preferences memories: actor_id=Alice, namespace=/sre/users/Alice/preferences, query='user settings communication escalation notification'
```

これはプランニングエージェントが以下を行うことを示しています：
1. **10 のユーザー好みを取得** Alice の好み namespace から
2. **50 のインフラストラクチャ知識項目を取得** 蓄積されたエージェント調査から
3. **5 つの過去の調査を取得** 類似のクエリパターン用
4. **retrieve_memory ツールを使用** 構造化クエリでプランニング前にコンテキストを収集

#### メモリコンテキスト付きの強化されたプランニングプロンプト

プランニングプロンプトは現在、より良い Claude インタラクションのために XML 構造を使用しています：

```xml
<memory_retrieval>
CRITICAL: 調査計画を作成する前に、retrieve_memory ツールを使用して関連コンテキストを収集する必要があります：
1. retrieve_memory("preference", "user settings communication escalation notification", "{user_id}", 5) を使用
2. retrieve_memory("infrastructure", "[クエリからの関連サービス用語]", "sre-agent", 10, null) を使用
3. retrieve_memory("investigation", "[ユーザークエリからのキーワード]", "{user_id}", 5, null) を使用
</memory_retrieval>

<planning_guidelines>
メモリコンテキストを収集した後、最大 2-3 ステップのシンプルで焦点を絞った調査計画を作成します。
メモリからのユーザー好みと過去の調査パターンを考慮してください。
</planning_guidelines>

<response_format>
必須: レスポンスはこの正確な構造に一致する有効な JSON のみである必要があります：
{
  "steps": ["ステップ 1 の説明", "ステップ 2 の説明"],
  "agents_sequence": ["kubernetes_agent", "logs_agent"],
  "complexity": "simple",
  "auto_execute": true,
  "reasoning": "取得したメモリコンテキストに基づく簡潔な説明"
}
</response_format>
```

#### メモリ情報に基づくプランニング例

```python
# 強化されたプランニングプロンプトには以下が含まれます：
"""
ユーザーのクエリ: kubernetes pods をリスト

取得したメモリコンテキスト：
- ユーザー好み (10 項目): シンプルな Kubernetes 計画の自動承認、技術詳細の好み
- インフラストラクチャ知識 (50 項目): 本番 namespace レイアウト、Pod 依存関係パターン
- 過去の調査 (5 項目): 以前の成功した Pod リスト調査

このコンテキストを考慮して調査計画を作成...
"""
```

プランニングエージェントは次のような計画を作成します：
```json
{
  "steps": ["Kubernetes エージェントを使用してすべての namespace の現在の Pod ステータスを取得", "Pod の健全性とリソース使用率を分析", "Pod 詳細を含む構造化された技術レポートを提供"],
  "agents_sequence": ["kubernetes_agent"],
  "complexity": "simple",
  "auto_execute": true,
  "reasoning": "シンプルな Kubernetes 計画の自動承認に対するユーザー好みと過去の成功した調査に基づき、これは Kubernetes エージェントのみを必要とする簡単な Pod リストタスクです"
}
```

## メモリキャプチャとパターン認識

SRE エージェントは、高度なパターン認識と構造化データ変換プロセスを通じて調査中に情報を自動的にキャプチャします：

### メモリキャプチャの仕組み

SRE エージェントコード（特に `sre_agent/memory/hooks.py`）は、正規表現パターンを使用してエージェントレスポンスを解析し、構造化情報を抽出します：

1. **レスポンス分析**: 各エージェントレスポンス後、システムは特定のパターンをスキャン
2. **パターンマッチング**: 正規表現を使用して主要な情報タイプを特定
3. **データ構造化**: マッチしたパターンを構造化 Pydantic モデルに変換
4. **メモリストレージ**: Amazon Bedrock AgentCore Memory の `create_event()` API を呼び出して構造化データを保存

### SRE エージェントパターン認識

すべての個別エージェントレスポンスは `on_agent_response()` フックを通じて自動メモリパターン抽出をトリガーします。これにより、ドメイン固有の調査中に発見された貴重な情報がキャプチャされ、将来の使用のために利用可能になります。

### エージェント JSON レスポンスによるインフラストラクチャ知識抽出

システムはインフラストラクチャ知識抽出のために高度なエージェントベースのアプローチを使用します。各エージェントは構造化 JSON 形式を使用してレスポンスにインフラストラクチャ知識を含めるよう指示されています：

#### エージェントレスポンス形式
```json
{
  "infrastructure_knowledge": [
    {
      "service_name": "web-app-deployment",
      "knowledge_type": "baseline",
      "knowledge_data": {
        "cpu_usage_normal": "75%",
        "memory_usage_normal": "85%",
        "typical_pods": 1,
        "node_distribution": "node-1"
      },
      "confidence": 0.9,
      "context": "Pod ステータス分析で通常のリソース使用パターンが判明"
    }
  ]
}
```

#### キャプチャされる知識タイプ
- **dependency**: サービスの関係と依存関係
- **pattern**: 繰り返しのインフラストラクチャパターンと動作
- **config**: 設定インサイトと設定
- **baseline**: パフォーマンスベースラインと通常の動作範囲

#### 自動抽出プロセス
1. **エージェントレスポンス処理**: 各エージェントレスポンスは `infrastructure_knowledge` を含む JSON ブロックをスキャン
2. **JSON パース**: システムは JSON 構造を抽出して検証
3. **知識ストレージ**: 有効な知識項目はインフラストラクチャメモリ namespace に保存
4. **クロスセッション可用性**: 知識はすべてのセッションで将来の調査に利用可能

### 強化されたエージェントレスポンス処理とログ

#### 包括的なレスポンスログ
システムはエージェントレスポンスとメモリ操作の詳細なログを提供します：

```log
# agent.log より - メッセージ内訳ログ
2025-08-03 17:45:30,397,p1289365,{agent_nodes.py:347},INFO,Kubernetes Infrastructure Agent - Message breakdown: 1 USER, 1 ASSISTANT, 1 TOOL messages
2025-08-03 17:45:30,397,p1289365,{agent_nodes.py:349},INFO,Kubernetes Infrastructure Agent - Tools called: k8s-api___get_pod_status

# メモリパターン抽出ログ
2025-08-03 17:45:30,398,p1289365,{hooks.py:193},INFO,on_agent_response called for agent: Kubernetes Infrastructure Agent, user_id: Alice
2025-08-03 17:45:30,399,p1289365,{hooks.py:383},INFO,Extracted 5 infrastructure knowledge items from agent response
```

#### インフラストラクチャ知識検証
システムにはインフラストラクチャ知識抽出の検証とエラーハンドリングが含まれています：

```log
# 成功した抽出ログ
2025-08-03 17:45:30,401,p1289365,{hooks.py:387},INFO,Saved infrastructure knowledge: web-app-deployment (baseline) with confidence 0.9
2025-08-03 17:45:30,402,p1289365,{hooks.py:387},INFO,Saved infrastructure knowledge: database-pod (pattern) with confidence 0.8
```

#### 自動会話メモリストレージ
すべてのエージェントインタラクションはメッセージタイプ内訳付きで会話メモリに自動的に保存されます：

```log
# ツール追跡付き会話ストレージ
2025-08-03 17:45:30,397,p1289365,{agent_nodes.py:347},INFO,Kubernetes Infrastructure Agent - Message breakdown: 1 USER, 1 ASSISTANT, 1 TOOL messages
2025-08-03 17:45:30,397,p1289365,{agent_nodes.py:349},INFO,Kubernetes Infrastructure Agent - Tools called: k8s-api___get_pod_status
2025-08-03 17:45:30,530,p1289365,{agent_nodes.py:375},INFO,Kubernetes Infrastructure Agent: Successfully stored conversation in memory
```

#### クロスセッションメモリアクセス
システムはより良い調査コンテキストのためにクロスセッションメモリ取得を提供します：

```log
# クロスセッションインフラストラクチャ知識取得
2025-08-03 17:45:30,140,p1289365,{hooks.py:71},INFO,Retrieved infrastructure knowledge for user 'Alice' from 1 different sources: Alice: 50 memories
2025-08-03 17:45:30,140,p1289365,{client.py:245},INFO,Retrieved 50 infrastructure memories for Alice
```

### メモリキャプチャ方法
1. **Supervisor ツール呼び出し**: プランニング中に `retrieve_memory` を呼び出し、プランニングエージェント経由で `save_investigation` を呼び出し
2. **自動パターン抽出**: エージェントレスポンスは `on_agent_response()` フックによって処理され、以下を抽出：
   - ユーザー好み（エスカレーションメール、Slack チャネル）
   - インフラストラクチャ知識（サービス依存関係、ベースライン）
   - `_save_*` 関数を直接呼び出し（ツール呼び出しではない）
3. **手動設定**: `manage_memories.py update` 経由でユーザー好みをロード
4. **会話ストレージ**: すべてのエージェントレスポンスとツール呼び出しを会話メモリとして保存

### メモリストレージプロセス
1. **パターン検出**: SRE エージェントコードがレスポンス内の関連情報を特定
2. **データ変換**: 構造化オブジェクト（UserPreference、InfrastructureKnowledge など）を作成
3. **イベント作成**: actor_id と構造化データで `create_event()` を呼び出し
4. **Namespace ルーティング**: Amazon Bedrock AgentCore Memory は戦略設定に基づいて正しい namespace に自動ルーティング

## エージェントメモリ統合

メモリシステムは既存の SRE エージェントとシームレスに統合されます：

### Kubernetes エージェント
- **キャプチャ:** サービス依存関係、デプロイメントパターン、リソースベースライン
- **使用:** 過去のデプロイメント問題、既知のリソース要件
- **キャプチャされる知識の例:**
  ```json
  {
    "service_name": "web-app-deployment",
    "knowledge_type": "baseline",
    "knowledge_data": {
      "cpu_usage_normal": "75%",
      "memory_usage_normal": "85%",
      "typical_pods": 1
    }
  }
  ```

### ログエージェント
- **キャプチャ:** 一般的なエラーパターン、ログクエリの好み、解決戦略
- **使用:** 類似のエラーパターン、過去の調査からの効果的なログクエリ
- **キャプチャされる知識の例:**
  ```json
  {
    "service_name": "payment-service",
    "knowledge_type": "pattern",
    "knowledge_data": {
      "common_errors": ["connection timeout", "memory leak"],
      "effective_queries": ["error AND payment AND timeout"]
    }
  }
  ```

### メトリクスエージェント
- **キャプチャ:** パフォーマンスベースライン、アラートしきい値、メトリクス相関
- **使用:** 履歴ベースライン、既知のパフォーマンスパターン
- **キャプチャされる知識の例:**
  ```json
  {
    "service_name": "api-gateway",
    "knowledge_type": "baseline",
    "knowledge_data": {
      "normal_response_time": "200ms",
      "peak_traffic_hours": "14:00-17:00 UTC"
    }
  }
  ```

### ランブックエージェント
- **キャプチャ:** 成功した解決手順、チームエスカレーションパス
- **使用:** 実証済みの解決戦略、適切なランブック推奨
- **キャプチャされる知識の例:**
  ```json
  {
    "service_name": "database",
    "knowledge_type": "dependency",
    "knowledge_data": {
      "escalation_team": "database-team@company.com",
      "recovery_runbook": "DB-001"
    }
  }
  ```

## 手動メモリ管理

メモリ管理は `manage_memories.py` スクリプトを通じて処理されます：

### メモリの表示
```bash
# すべてのメモリタイプをリスト
uv run python scripts/manage_memories.py list

# 特定のメモリタイプをリスト
uv run python scripts/manage_memories.py list --memory-type preferences

# 特定ユーザーのメモリをリスト
uv run python scripts/manage_memories.py list --memory-type preferences --actor-id Alice
```

### ユーザー好みの管理
```bash
# YAML 設定からユーザー好みをロード
uv run python scripts/manage_memories.py update

# カスタム設定ファイルからロード
uv run python scripts/manage_memories.py update --config-file custom_users.yaml
```

## メリット

- **パーソナライズされた調査:** 個々のユーザーの好みと役割に基づいてレポートとコミュニケーションをカスタマイズ
- **迅速な解決:** 履歴コンテキストと過去の調査知識を活用
- **知識の保存:** チーム変更を超えて部族的知識を自動的にキャプチャして共有
- **パターン認識:** 繰り返し発生する問題を特定し、エスカレーションルーティングを最適化
- **MTTR の削減:** 蓄積された組織知識を通じて問題解決を加速

## プライバシーとデータ管理

### データ保持
- ユーザー好み: 90 日（設定可能）
- インフラストラクチャ知識: 30 日（設定可能）
- 調査サマリー: 60 日（設定可能）

## メモリシステムのセットアップ

### 初期セットアップ

メモリシステムはセットアッププロセス中に自動的に初期化されます：

```bash
# メモリシステムを初期化してユーザー好みをロード（セットアップ手順に含まれる）
uv run python scripts/manage_memories.py update
```

このコマンドは：
1. 存在しない場合は新しいメモリリソースを作成
2. 3 つのメモリ戦略を設定
3. `scripts/user_config.yaml` からユーザー好みをロード
4. 将来使用するためにメモリ ID を `.memory_id` に保存

### ユーザー好みの追加

新しいユーザーを追加したり既存の好みを変更するには：

1. `scripts/user_config.yaml` を編集して新しいユーザー設定を追加
2. update コマンドを実行して新しい好みをロード：
```bash
uv run python scripts/manage_memories.py update
```

### メモリの管理

```bash
# すべてのメモリタイプをリスト
uv run python scripts/manage_memories.py list

# 特定のメモリタイプをリスト
uv run python scripts/manage_memories.py list --memory-type preferences

# 特定ユーザーの好みをリスト
uv run python scripts/manage_memories.py list --memory-type preferences --actor-id Alice
```
