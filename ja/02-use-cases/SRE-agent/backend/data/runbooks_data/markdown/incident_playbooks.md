# インシデントプレイブック

このドキュメントには、さまざまな種類の運用上の問題に対するインシデント対応プレイブックが含まれています。

## 高メモリ使用率インシデント対応

**プレイブック ID:** `memory-pressure-playbook`
**インシデントタイプ:** パフォーマンス
**重大度:** 高
**推定解決時間:** 15-30 分

### 説明
高メモリ使用率インシデントを処理するための手順

### トリガー
- メモリ使用率 > 85%
- ログに OutOfMemoryError
- メモリ圧迫による Pod の退避

### 対応手順
1. 影響を受けた Pod を特定: `kubectl get pods --field-selector=status.phase=Running`
2. メモリ使用量を確認: `kubectl top pods -n production`
3. 最近のメモリメトリクスとトレンドをレビュー
4. 水平スケーリングが可能な場合はデプロイメントをスケールアップ
5. デプロイメント設定でメモリ制限を増加
6. 必要に応じて影響を受けた Pod を再起動
7. 復旧を監視し、正常な動作を確認

### エスカレーション
- **プライマリ:** on-call-engineer
- **セカンダリ:** platform-team
- **マネージャー:** engineering-manager

### 関連ランブック
- pod-crashloop-troubleshooting
- resource-optimization

---

## データベース接続障害対応

**プレイブック ID:** `database-connection-failure`
**インシデントタイプ:** 可用性
**重大度:** クリティカル
**推定解決時間:** 5-15 分

### 説明
データベース接続の問題を処理するための手順

### トリガー
- データベース接続タイムアウトエラー
- コネクションプールの枯渇
- CrashLoopBackOff 状態のデータベース Pod

### 対応手順
1. データベース Pod のステータスを確認: `kubectl get pods -l app=database`
2. データベースログをレビュー: `kubectl logs -f database-pod-name`
3. データベースサービスエンドポイントを検証
4. サービス間のネットワーク接続性を確認
5. 設定が正しい場合はデータベース Pod を再起動
6. 必要に応じてコネクションプールをスケール
7. アプリケーションがデータベースに接続できることを確認

### エスカレーション
- **プライマリ:** database-admin
- **セカンダリ:** infrastructure-team
- **マネージャー:** site-reliability-manager

### 関連ランブック
- database-recovery
- connection-pool-tuning

---

## 高エラーレート対応

**プレイブック ID:** `high-error-rate-response`
**インシデントタイプ:** 可用性
**重大度:** 高
**推定解決時間:** 10-20 分

### 説明
エラーレート増加を処理するための手順

### トリガー
- エラーレート > 10%
- 5xx エラーの増加
- 複数サービスの障害

### 対応手順
1. すべてのサービスにわたる現在のエラーレートを確認
2. エラーの原因となっているソースサービスを特定
3. エラーパターンに関するアプリケーションログをレビュー
4. 最近のデプロイメントまたは設定変更を確認
5. 最近のデプロイメントの場合はロールバックを検討
6. 負荷に関連する場合は影響を受けたサービスをスケール
7. カスケード障害の場合はサーキットブレーカーを有効化

### エスカレーション
- **プライマリ:** on-call-engineer
- **セカンダリ:** service-owner
- **マネージャー:** engineering-manager

### 関連ランブック
- rollback-procedures
- circuit-breaker-configuration

---

## Pod 起動失敗解決

**プレイブック ID:** `pod-startup-failure`
**インシデントタイプ:** デプロイメント
**重大度:** 中
**推定解決時間:** 10-30 分

### 説明
Pod 起動の問題を解決するための手順

### トリガー
- Pending 状態でスタックした Pod
- ImagePullBackOff エラー
- Init コンテナの失敗

### 対応手順
1. Pod イベントを確認: `kubectl describe pod <pod-name>`
2. イメージの可用性とプルシークレットを検証
3. リソースクォータと制限を確認
4. 該当する場合は Init コンテナのログをレビュー
5. ConfigMap とシークレットを検証
6. ノードリソースとスケジューリング制約を確認
7. 修正した設定で Pod を再作成

### エスカレーション
- **プライマリ:** platform-team
- **セカンダリ:** infrastructure-team
- **マネージャー:** platform-manager

### 関連ランブック
- kubernetes-troubleshooting
- deployment-best-practices

---

## データベース Pod CrashLoopBackOff インシデント

**プレイブック ID:** `database-pod-crashloop-incident`
**インシデントタイプ:** 可用性
**重大度:** クリティカル
**推定解決時間:** 10-15 分
**特定の Pod:** `database-pod-7b9c4d8f2a-x5m1q`

### 説明
データベース Pod が継続的にクラッシュする場合のクリティカルインシデント対応

### 根本原因
PostgreSQL の初期化を妨げる 'database-config' ConfigMap の欠落

### トリガー
- CrashLoopBackOff 状態のデータベース Pod
- ConfigMap 'database-config' not found エラー
- PostgreSQL 初期化の失敗
- ボリュームマウント権限エラー

### 対応手順
1. **即時:** Pod のステータスを確認: `kubectl get pod database-pod-7b9c4d8f2a-x5m1q -n production`
2. Pod ログをレビュー: `kubectl logs database-pod-7b9c4d8f2a-x5m1q --previous -n production`
3. ConfigMap の存在を検証: `kubectl get configmap database-config -n production`
4. ConfigMap が欠落している場合は作成:
   ```bash
   kubectl create configmap database-config \
     --from-literal=database.conf='shared_buffers=256MB\nmax_connections=100\nlog_destination=stderr' \
     -n production
   ```
5. ボリューム権限を確認: `kubectl exec -it database-pod-7b9c4d8f2a-x5m1q -- ls -la /var/lib/postgresql/`
6. Pod を強制再起動: `kubectl delete pod database-pod-7b9c4d8f2a-x5m1q -n production`
7. Pod の起動を監視: `kubectl logs database-pod-7b9c4d8f2a-x5m1q -f -n production`
8. 稼働後にデータベース接続性を検証

### 影響評価
- **影響を受けるサービス:** web-service, api-service
- **影響を受けるユーザー:** 全ユーザー - 完全なデータベース停止
- **ビジネスへの影響:** クリティカル - データ操作が不可能

### エスカレーション
- **プライマリ:** database-oncall@company.com
- **セカンダリ:** platform-oncall@company.com
- **マネージャー:** incident-manager@company.com
- **エスカレーション時間:** 5 分

### 関連ランブック
- database-crashloop-troubleshooting
- configmap-management

### インシデント後のアクション
- デプロイメントマニフェストに ConfigMap を追加
- CI/CD で ConfigMap 検証を実装
- ConfigMap の存在確認の監視を追加
- 設定要件を文書化
