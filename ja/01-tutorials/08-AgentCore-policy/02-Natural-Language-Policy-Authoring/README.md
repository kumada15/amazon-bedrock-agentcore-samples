# AgentCore Policy - 自然言語ポリシー作成（NL2Cedar）

Amazon Bedrock AgentCore Policy の NL2Cedar 機能を使用して、自然言語から Cedar ポリシーを生成するハンズオンデモです。

## 🚀 クイックスタート

1. **依存関係のインストール**: `pip install -r requirements.txt`
2. **ノートブックを開く**: `jupyter notebook NL-Authoring-Policy.ipynb`
3. **ノートブックの手順に従う**

> **注意**: このデモは Getting-Started チュートリアルを基に構築されています。まだ完了していない場合、ノートブックが自動的に必要なインフラストラクチャをセットアップします。

## 概要

このデモでは、自然言語で認可要件を記述し、自動的に Cedar 構文に変換する方法を紹介します。NL2Cedar 機能により、以下が可能になります：

- Cedar 構文の代わりにプレーンな日本語/英語でポリシーを記述
- 複数行のステートメントから複数のポリシーを生成
- アイデンティティ属性を持つプリンシパルベースのポリシーを作成
- 生成されたポリシーが要件に一致することを確認

## 学習内容

- ✅ 自然言語の説明から Cedar ポリシーを生成
- ✅ 単純な単一ステートメントポリシーの作成
- ✅ 複数行のステートメントから複数のポリシーを生成
- ✅ アイデンティティ属性を持つプリンシパルスコープポリシーの作成
- ✅ 異なるポリシー構成とパターンの理解

## 前提条件

開始前に、以下を確認してください：

- 適切な認証情報で設定された AWS CLI
- boto3 1.42.0+ がインストールされた Python 3.10+
- `bedrock_agentcore_starter_toolkit` パッケージがインストール済み
- AWS Lambda へのアクセス（ターゲット関数用）
- **01-Getting-Started** チュートリアルを完了（またはノートブックに自動セットアップさせる）

## デモシナリオ

このデモでは、Getting-Started チュートリアルの**保険引受処理システム**を使用し、3つの Lambda ツールがあります：

1. **ApplicationTool** - 保険申請を作成
   - パラメータ: `applicant_region`、`coverage_amount`

2. **RiskModelTool** - リスクスコアリングモデルを呼び出し
   - パラメータ: `API_classification`、`data_governance_approval`

3. **ApprovalTool** - 引受決定を承認
   - パラメータ: `claim_amount`、`risk_level`

## 自然言語ポリシーの例

### 1. 単純な単一ステートメントポリシー

**自然言語：**
```
補償額が100万ドル未満で、申請地域が US または CAN の場合、
すべてのユーザーに application tool の呼び出しを許可
```

**生成された Cedar ポリシー：**
```cedar
permit(
  principal,
  action == AgentCore::Action::"ApplicationToolTarget___create_application",
  resource == AgentCore::Gateway::"<gateway-arn>"
) when {
  (context.input.coverage_amount < 1000000) &&
  ((context.input.applicant_region == "US") ||
   (context.input.applicant_region == "CAN"))
};
```

### 2. 複数行ステートメント

**自然言語：**
```
data governance approval が true の場合、すべてのユーザーに risk model tool の呼び出しを許可。
coverage amount が存在しない場合、ユーザーが application tool を呼び出すことをブロック。
```

**結果：** **2つの別々のポリシー**が生成されます - 1つは permit ポリシー、1つは forbid ポリシー。

### 3. プリンシパルベースのポリシー

**自然言語：**
```
username が "test-user" のプリンシパルに risk model tool の呼び出しを許可
```

**生成された Cedar ポリシー：**
```cedar
permit(
  principal,
  action == AgentCore::Action::"RiskModelToolTarget___invoke_risk_model",
  resource == AgentCore::Gateway::"<gateway-arn>"
) when {
  (principal.hasTag("username")) &&
  (principal.getTag("username") == "test-user")
};
```

**自然言語：**
```
scope group:Controller を持っていない場合、プリンシパルが approval tool にアクセスすることを禁止
```

**生成された Cedar ポリシー：**
```cedar
forbid(
  principal,
  action == AgentCore::Action::"ApprovalToolTarget",
  resource == AgentCore::Gateway::"<gateway-arn>"
) when {
  !((principal.hasTag("scope")) &&
    (principal.getTag("scope") like "*group:Controller*"))
};
```

**自然言語：**
```
プリンシパルが role "senior-adjuster" を持っていない場合、
risk model tool と approval tool の使用をブロック
```

**生成された Cedar ポリシー：**
```cedar
forbid(
  principal,
  action in [AgentCore::Action::"RiskModelToolTarget",
             AgentCore::Action::"ApprovalToolTarget"],
  resource == AgentCore::Gateway::"<gateway-arn>"
) when {
  !((principal.hasTag("role")) &&
    (principal.getTag("role") == "senior-adjuster"))
};
```

## NL2Cedar の仕組み

1. **スキーマ認識**: Gateway ターゲットスキーマが NL2Cedar に提供され、基盤モデルがツール名とパラメータを理解できるようになります

2. **自然言語入力**: プレーンな日本語/英語で認可要件を提供します

3. **Cedar 生成**: システムが構文的に正しい Cedar ポリシーを生成します

4. **ポリシー作成**: 生成されたポリシーは Policy Engine で直接作成できます

## ワークフロー

ノートブックは以下をガイドします：

1. **環境セットアップ** - 認証情報と依存関係の確認
2. **インフラストラクチャチェック** - 必要に応じて Gateway を自動セットアップ（Getting-Started から）
3. **Policy Engine 作成** - NL2Cedar ポリシー用の Policy Engine を作成
4. **単純なポリシー生成** - 自然言語から単一のポリシーを生成
5. **ポリシー作成** - Policy Engine で生成されたポリシーを作成
6. **複数行生成** - 複数行のステートメントから複数のポリシーを生成
7. **プリンシパルベースのポリシー** - アイデンティティ認識ポリシーの作成
8. **クリーンアップ** - 作成されたすべてのリソースを削除

## 主な機能

### 自動インフラストラクチャセットアップ

Getting-Started チュートリアルを完了していない場合、ノートブックは以下を行います：
- 3つの Lambda 関数をデプロイ（ApplicationTool、RiskModelTool、ApprovalTool）
- OAuth 認証で AgentCore Gateway を作成
- 適切なスキーマで Lambda ターゲットを設定
- 設定を `config.json` に保存

### 複数ポリシー生成

一貫した区切り文字（カンマ、ピリオド、セミコロン）を持つ複数行のステートメントを提供すると、NL2Cedar は自動的に：
- 個別のポリシーステートメントを検出
- 各ステートメントに対して別々の Cedar ポリシーを生成
- `generatedPolicies` 配列ですべてのポリシーを返す

### プリンシパルスコープサポート

アイデンティティベースのポリシーでは、以下を参照できます：
- **ユーザー名**: `principal.getTag("username")`
- **ロール**: `principal.getTag("role")`
- **スコープ**: `principal.getTag("scope")`
- **カスタムクレーム**: OAuth トークンの任意の属性

> **💡 ヒント**: 自然言語ステートメントで正確なタグ名を指定すると、NL2Cedar が正しい Cedar ポリシーを作成するのに役立ちます。


## ベストプラクティス

1. **具体的に記述**: ツール名、パラメータ、条件を明確に記述する
2. **正確なパラメータ名を使用**: Gateway スキーマに表示されるとおりにパラメータを参照する
3. **プリンシパル属性を指定**: アイデンティティベースのポリシーでは、正確なタグ名を記述する
4. **1行に1つのコンセプト**: 複数行生成では、一貫した区切り文字で別々のポリシーを分離する
5. **生成されたポリシーをテスト**: デプロイ前に常に生成された Cedar 構文を確認する



## その他のリソース

- **ポリシー例**: [サポートされている Cedar ポリシー](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/example-policies.html)
- **Getting Started チュートリアル**: `../01-Getting-Started/README.md`

---

**ハッピービルディング！** 🚀
