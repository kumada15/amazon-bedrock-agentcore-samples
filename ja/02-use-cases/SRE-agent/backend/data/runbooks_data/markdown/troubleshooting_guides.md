# トラブルシューティングガイド

このドキュメントには、一般的な運用上の問題に対する詳細なトラブルシューティングガイドが含まれています。

## Pod CrashLoopBackOff トラブルシューティング

**ガイド ID:** `pod-crashloop-troubleshooting`
**カテゴリ:** Kubernetes

### トラブルシューティング手順
1. Pod の詳細を取得: `kubectl describe pod <pod-name>`
2. Pod ログを確認: `kubectl logs <pod-name> --previous`
3. 最近のイベントを確認: `kubectl get events --sort-by=.metadata.creationTimestamp`
4. リソースの limits と requests を検証
5. liveness と readiness プローブを確認
6. コンテナイメージと設定をレビュー
7. 環境変数とシークレットを検証

### 一般的な原因
- リソース不足（CPU/メモリ）
- liveness プローブ設定の誤り
- 環境変数の欠落
- 無効なコンテナイメージまたはタグ
- デプロイメントの設定エラー

### 診断コマンド
- `kubectl get pod <pod-name> -o yaml`
- `kubectl logs <pod-name> --previous`
- `kubectl describe pod <pod-name>`
- `kubectl get events --field-selector involvedObject.name=<pod-name>`

---

## データベース Pod CrashLoopBackOff 解決

**ガイド ID:** `database-crashloop-troubleshooting`
**カテゴリ:** Kubernetes
**特定の Pod:** `database-pod-7b9c4d8f2a-x5m1q`

### トラブルシューティング手順
1. Pod ログを確認: `kubectl logs database-pod-7b9c4d8f2a-x5m1q --previous`
2. ConfigMap の存在を検証: `kubectl get configmap database-config -n production`
3. ボリュームマウントを確認: `kubectl describe pod database-pod-7b9c4d8f2a-x5m1q`
4. PVC ステータスを検証: `kubectl get pvc -n production`
5. データディレクトリの権限を確認
6. 必要に応じて欠落している ConfigMap を作成: `kubectl create configmap database-config --from-file=database.conf`
7. ボリューム権限を修正: `chmod 700 /var/lib/postgresql/data && chown postgres:postgres /var/lib/postgresql/data`

### 一般的な原因
- 'database-config' ConfigMap の欠落
- データディレクトリのファイル権限の誤り
- ボリュームマウントの失敗
- データベース設定ファイルの欠落
- PostgreSQL 初期化の失敗

### 診断コマンド
- `kubectl logs database-pod-7b9c4d8f2a-x5m1q -c postgres --previous`
- `kubectl describe pod database-pod-7b9c4d8f2a-x5m1q`
- `kubectl get configmap -n production | grep database`
- `kubectl get pvc -n production`
- `kubectl get events --field-selector involvedObject.name=database-pod-7b9c4d8f2a-x5m1q --sort-by='.lastTimestamp'`

### 解決方法

#### 即時修正
```bash
kubectl create configmap database-config \
  --from-literal=database.conf='shared_buffers=256MB\nmax_connections=100' \
  -n production
```

#### 恒久修正
適切な ConfigMap とボリューム権限を含めるようにデプロイメントマニフェストを更新

**影響:** クリティカル - すべてのサービスに影響を与える完全なデータベース停止
**推定解決時間:** 10-15 分

---

## 高レスポンスタイム調査

**ガイド ID:** `high-response-time-troubleshooting`
**カテゴリ:** パフォーマンス

### 調査手順
1. 現在のレスポンスタイムメトリクスを確認
2. 影響を受けるエンドポイントとサービスを特定
3. CPU とメモリ使用率をレビュー
4. データベースクエリのパフォーマンスを調査
5. ネットワークレイテンシの問題を確認
6. ボトルネックに関するアプリケーションログをレビュー
7. 外部サービスの依存関係を検証

### ツール
- `kubectl top pods`
- アプリケーションパフォーマンス監視（APM）
- データベースクエリ分析ツール
- ネットワーク監視ツール

### 一般的な原因
- データベースクエリの最適化が必要
- サービスリソースの不足
- ネットワークレイテンシまたはパケットロス
- 外部サービスの劣化
- キャッシュミスまたは無効化

---

## メモリリーク調査ガイド

**ガイド ID:** `memory-leak-investigation`
**カテゴリ:** パフォーマンス

### 調査手順
1. 時間経過に伴うメモリ使用量のトレンドを監視
2. メモリ使用量が増加しているサービスを特定
3. 可能であればヒープダンプをキャプチャ
4. 最近のコード変更をレビュー
5. 閉じられていないリソースを確認
6. オブジェクト割り当てパターンを分析
7. ステージング環境で修正をテスト

### 診断コマンド
- `kubectl top pods --containers`
- `kubectl exec <pod> -- jmap -heap <pid>`
- `kubectl exec <pod> -- jstat -gcutil <pid>`

### 予防措置
- 適切なリソースクリーンアップを実装
- コネクションプーリングを使用
- 適切な JVM ヒープ設定を構成
- メモリメトリクスを継続的に監視

---

## サービスディスカバリのトラブルシューティング

**ガイド ID:** `service-discovery-issues`
**カテゴリ:** ネットワーキング

### トラブルシューティング手順
1. サービスエンドポイントを検証: `kubectl get endpoints`
2. サービスセレクターラベルを確認
3. Pod からの DNS 解決をテスト
4. ネットワークポリシーを検証
5. サービスポート設定を確認
6. Pod 間の接続性をテスト
7. イングレス設定をレビュー

### 診断コマンド
- `kubectl get svc <service-name> -o yaml`
- `kubectl get endpoints <service-name>`
- `kubectl exec <pod> -- nslookup <service-name>`
- `kubectl exec <pod> -- curl <service-name>:<port>`

### 一般的な問題
- セレクターラベルの不一致
- ポート設定の誤り
- ネットワークポリシーの制限
- DNS 設定の問題
