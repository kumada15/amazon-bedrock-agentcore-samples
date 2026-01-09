# サービスリカバリー手順

このドキュメントには、さまざまなサービスおよび完全なスタックリカバリープロセスのためのリカバリー手順が含まれています。

## Web サービスリカバリー

**リカバリー ID:** `web-service-recovery`
**サービス:** web-service

### リカバリー手順

#### ステップ 1: サービスヘルスを確認
- **コマンド:** `kubectl get pods -l app=web-app`
- **期待される結果:** すべての Pod が Running 状態であること

#### ステップ 2: 異常な Pod を再起動
- **コマンド:** `kubectl delete pod <unhealthy-pod-name>`
- **期待される結果:** 新しい Pod が起動し、準備完了になること

#### ステップ 3: 必要に応じてデプロイメントをスケール
- **コマンド:** `kubectl scale deployment web-app-deployment --replicas=5`
- **期待される結果:** 追加の Pod が起動すること

#### ステップ 4: ロードバランサーを検証
- **コマンド:** `kubectl get svc web-app-service`
- **期待される結果:** 外部 IP が割り当てられていること

#### ステップ 5: サービスエンドポイントをテスト
- **コマンド:** `curl http://<external-ip>/health`
- **期待される結果:** 200 OK を返すこと

### ロールバック手順

**トリガー:** 30 分後もリカバリーが失敗した場合

#### ロールバック手順
1. 前のデプロイメントリビジョンを取得: `kubectl rollout history deployment/web-app-deployment`
2. 前のバージョンにロールバック: `kubectl rollout undo deployment/web-app-deployment`
3. ロールバックステータスを監視: `kubectl rollout status deployment/web-app-deployment`
4. ロールバック後にサービスヘルスを検証

---

## データベースリカバリー

**リカバリー ID:** `database-recovery`
**サービス:** database

### リカバリー手順

#### ステップ 1: データベース Pod のステータスを確認
- **コマンド:** `kubectl get pods -l app=database`
- **期待される結果:** Pod が Running 状態であること

#### ステップ 2: Persistent Volume を検証
- **コマンド:** `kubectl get pv,pvc -n production`
- **期待される結果:** PVC がバインドされていること

#### ステップ 3: データベースログを確認
- **コマンド:** `kubectl logs -f database-pod-name`
- **期待される結果:** クリティカルエラーがないこと

#### ステップ 4: データベース接続性をテスト
- **コマンド:** `kubectl exec -it database-pod -- psql -U postgres -c 'SELECT 1'`
- **期待される結果:** クエリが正常に返ること

#### ステップ 5: 該当する場合はレプリケーションを検証
- **コマンド:** `kubectl exec -it database-pod -- psql -U postgres -c 'SELECT * FROM pg_stat_replication'`
- **期待される結果:** レプリカが接続されていること

### データリカバリー

**バックアップ場所:** s3://backup-bucket/database/

#### リストア手順
1. アプリケーションの書き込みを停止
2. 空のボリュームで新しいデータベース Pod を作成
3. 最新のバックアップからリストア: `pg_restore -d dbname backup.dump`
4. データの整合性を検証
5. アプリケーショントラフィックを再開

---

## 完全なスタックリカバリー

**リカバリー ID:** `full-stack-recovery`
**タイトル:** 完全なスタックリカバリー

### サービス優先順位
1. database
2. cache-service
3. api-service
4. web-service
5. ingress-controller

### リカバリー前のチェック
- クラスターの健全性を検証: `kubectl get nodes`
- リソースの可用性を確認: `kubectl top nodes`
- 最近のイベントをレビュー: `kubectl get events --sort-by=.metadata.creationTimestamp`

### リカバリーフェーズ

#### フェーズ 1: インフラストラクチャ
- ノードの健全性を検証
- ネットワーク接続性を確認
- ストレージの可用性を確保

#### フェーズ 2: データ層
- データベースサービスをリカバリー
- データの整合性を検証
- 必要に応じてキャッシュをリストア

#### フェーズ 3: アプリケーション層
- バックエンドサービスを起動
- サービスディスカバリを検証
- フロントエンドサービスを起動

#### フェーズ 4: 検証
- ヘルスチェックを実行
- スモークテストを実施
- メトリクスを監視
