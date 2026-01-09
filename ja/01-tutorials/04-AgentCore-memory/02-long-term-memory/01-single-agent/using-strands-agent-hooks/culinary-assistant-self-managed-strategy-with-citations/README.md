# セルフマネージドメモリ戦略を使用した料理アシスタント（引用付き）

このサンプルは、強化された引用追跡機能を備えた Amazon Bedrock AgentCore のセルフマネージドメモリ戦略を示します。このバージョンは、抽出された長期メモリに包括的な引用情報を追加することで、基本の料理アシスタント例を拡張しています。

## 相違点

このサンプルは、抽出されたメモリのソースを追跡する引用機能を追加しています：

### 引用機能

1. **ソース追跡**: 抽出された各メモリにはその起源に関するメタデータが含まれます：
   - セッション ID とアクター ID
   - 開始および終了タイムスタンプ
   - 元の短期メモリペイロードが保存されている S3 URI
   - 抽出ジョブ ID

2. **引用メタデータ**: 構造化された引用情報がメモリメタデータに保存されます：
   ```python
   citation_info = {
       'source_type': 'short_term_memory',
       'session_id': session_id,
       'actor_id': actor_id,
       'starting_timestamp': starting_timestamp,
       'ending_timestamp': timestamp,
       's3_uri': s3_location,
       's3_payload_location': s3_location,
       'extraction_job_id': job_id
   }
   ```

3. **人間が読める引用**: 各メモリコンテンツには引用テキストが追加されます：
   ```
   [Citation: Extracted from session {session_id}, actor {actor_id}, source: {s3_location}, job: {job_id}, timestamp: {timestamp}]
   ```

### 変更されたファイル

#### `lambda_function.py`

主な変更は `MemoryExtractor` クラスにあります：

- `extract_memories()` メソッドは `s3_location` と `job_id` パラメータを受け付けるようになりました
- `_format_extracted_memories()` メソッドは引用情報を構築し、メモリコンテンツに追加します
- 引用情報を追跡するための強化されたログ記録

**キーメソッド**: `_format_extracted_memories`（97行目）
このメソッドは、抽出されたメモリをメタデータと引用情報でフォーマットし、長期メモリから短期メモリ内のソースへの追跡可能なリンクを作成します。

#### `agentcore_self_managed_memory_demo.ipynb`

引用機能の動作を示すように更新され、抽出されたメモリにソース帰属が含まれるようになったことを示しています。

## ユースケース

この引用強化バージョンは、以下の場合に特に有用です：

1. **監査証跡**: メモリの起源の完全な記録を維持
2. **デバッグ**: 元の会話コンテキストへのトレースバック
3. **コンプライアンス**: データリネージとソース帰属の要件を満たす
4. **メモリ検証**: S3 内の元のソースに対してメモリコンテンツを検証する機能

## 前提条件

基本の料理アシスタント例と同じです：
- Python 3.11 以上
- AWS 認証情報の設定
- Claude モデルを使用した Amazon Bedrock アクセス
- 必要な AWS サービス: Lambda、S3、SNS、SQS

## セットアップ

基本の料理アシスタント例と同じセットアッププロセスに従ってください。ノートブックは以下の手順をガイドします：

1. 引用サポート付きの Lambda 関数の作成
2. トリガー条件付きのメモリ戦略のセットアップ
3. 強化された引用機能のテスト

## 基本サンプルとの比較

| 機能 | 基本サンプル | 引用付き |
|---------|------------|----------------|
| メモリ抽出 | ✅ | ✅ |
| S3 ペイロード追跡 | ❌ | ✅ |
| ソース帰属 | ❌ | ✅ |
| ジョブ ID 追跡 | ❌ | ✅ |
| タイムスタンプコンテキスト | ❌ | ✅ |
| 引用メタデータ | ❌ | ✅ |

## ドキュメント

セルフマネージドメモリ戦略の詳細については、[Amazon Bedrock AgentCore ドキュメント](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-self-managed-strategies.html)を参照してください。
