# Amazon Bedrock AgentCore Tools

## 概要
Amazon Bedrock AgentCore Tools は、AIエージェントが複雑なタスクを安全かつ効率的に実行する能力を強化する、エンタープライズグレードの機能を提供します。このスイートには2つの主要なツールが含まれています：

- Amazon Bedrock AgentCore Code Interpreter
- Amazon Bedrock AgentCore Browser Tool

## Amazon Bedrock AgentCore Code Interpreter

### 主な機能

1. **安全なコード実行**：内部データソースにアクセスしながら、セキュリティを確保する隔離されたサンドボックス環境でコードを実行。

2. **フルマネージドのAWSネイティブソリューション**：Strands Agents、LangGraph、CrewAI などのフレームワークとシームレスに統合。

3. **高度な設定サポート**：入出力両方の大容量ファイルサポートとインターネットアクセスを含む。

4. **複数言語サポート**：JavaScript、TypeScript、Python を含む様々なプログラミング言語用のプリビルトランタイムモード。

### メリット

- **エージェント精度の向上**：エージェントが複雑な計算とデータ処理を実行できるようにする。
- **エンタープライズグレードのセキュリティ**：隔離された環境で厳格なセキュリティ要件を満たす。
- **効率的なデータ処理**：Amazon S3 のファイルを参照することでギガバイト規模のデータを処理可能。

## Amazon Bedrock AgentCore Browser Tool

### 主な機能

1. **モデル非依存の柔軟性**：Anthropic の Claude、OpenAI のモデル、Amazon の Nova モデルなど、さまざまなAIモデルからのコマンド構文をサポート。

2. **エンタープライズグレードのセキュリティ**：VM レベルの分離、VPC 接続、エンタープライズ SSO システムとの統合を提供。

3. **包括的な監査機能**：すべてのブラウザコマンドの CloudTrail ログ記録とセッション記録機能を含む。

### メリット

- **エンドツーエンドの自動化**：以前は手動介入が必要だった複雑なウェブワークフローをAIエージェントが自動化できるようにする。
- **セキュリティ強化**：広範なセキュリティ機能と監査機能でエンタープライズ要件を満たす。
- **リアルタイムモニタリング**：即時介入のためのライブビューとデバッグ・監査のためのセッションリプレイを提供。

## ユースケース

- 安全な環境での複雑なデータ分析と可視化
- フォーム入力、データ抽出、マルチステッププロセスのための自動化されたウェブインタラクション
- 大規模データ処理とモニタリング
- エンタープライズ環境でのAIエージェント用の安全なコード実行

## チュートリアル概要

1. [Amazon Bedrock AgentCore Code Interpreter](01-Agent-Core-code-interpreter)
2. [Amazon Bedrock AgentCore Browser Tool](02-Agent-Core-browser-tool)
