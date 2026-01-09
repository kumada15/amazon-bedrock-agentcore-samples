# Amazon Bedrock AgentCore 用 Policy

## 概要

Amazon Bedrock AgentCore 用 Policy は、Cedar ポリシーを使用して AI エージェントのきめ細かなアクセス制御を可能にします。JWT トークンのクレームを評価して、ツール呼び出しを許可または拒否するかを決定します。

### アーキテクチャ

```
                                ┌───────────────────────┐
                                │  Policy for AgentCore │
                                │  (Cedar ポリシー)     │
                                │                       │
                                │  評価対象:            │
                                │  - principal タグ     │
                                │  - context.input      │
                                │  - resource           │
                                └───────────┬───────────┘
                                            │ アタッチ
                                            ▼
┌─────────────────┐             ┌───────────────────────┐             ┌─────────────┐
│   Amazon        │  JWT Token  │  Amazon Bedrock       │             │   Lambda    │
│   Cognito       │────────────▶│  AgentCore Gateway    │────────────▶│   Target    │
│   + AWS Lambda  │  クレーム付 │                       │  許可の場合 │   (Tool)    │
└─────────────────┘             └───────────────────────┘             └─────────────┘
```

### チュートリアル詳細

| 情報                 | 詳細                                                    |
|:--------------------|:--------------------------------------------------------|
| AgentCore コンポーネント | Gateway、Identity、Policy                               |
| 例の複雑さ           | 中級                                                    |
| 使用 SDK             | boto3、requests                                         |

## 前提条件

- 適切な IAM 権限を持つ AWS アカウント
- OAuth オーソライザーを持つ Amazon Bedrock AgentCore Gateway
- Amazon Cognito User Pool（M2M クライアント、**Essentials** または **Plus** ティア）
- Python 3.8+

## はじめに

### オプション 1: セットアップスクリプト（新規リソース）

```bash
pip install bedrock-agentcore-starter-toolkit
python setup-gateway.py
```

### オプション 2: 既存リソース

Gateway と Cognito の詳細を含む `gateway_config.json` を作成します（テンプレートはノートブックを参照）。

### チュートリアルの実行

[policy_for_agentcore_tutorial.ipynb](policy_for_agentcore_tutorial.ipynb) を開きます

## Cedar ポリシー構文

| パターン | Cedar 構文 |
|---------|-------------|
| クレームの存在確認 | `principal.hasTag("claim_name")` |
| 完全一致 | `principal.getTag("claim_name") == "value"` |
| パターンマッチ | `principal.getTag("claim_name") like "*value*"` |
| 入力検証 | `context.input.field <= value` |

## テストシナリオ

1. **部署ベース** - 特定の部署のユーザーのみを許可
2. **グループベース** - 特定のグループのユーザーを許可（パターンマッチング）
3. **プリンシパル ID ベース** - 特定のクライアントアプリケーションを許可
4. **複合条件** - 入力検証を含む複数の条件

## ベストプラクティス

- エラーを回避するため、`getTag()` の前に `hasTag()` を使用する
- パターンマッチングは慎重に使用 - `like "*value*"` は意図しない文字列にもマッチする可能性がある
- ALLOW と DENY の両方のシナリオをテストする
- M2M クライアントクレデンシャルフローには V3_0 Lambda トリガーを使用する
