# エージェント機能ガイド

## 概要

コンシェルジュエージェントシステムは、包括的な旅行計画とショッピング支援を提供するために連携する3つの専門エージェントで構成されています：

1. **Supervisor Agent** - すべてのインタラクションを調整するメインオーケストレーター
2. **Travel Assistant** - 旅行計画、予約、目的地情報を処理
3. **Cart Manager** - ショッピングカート、決済、購入フローを管理

---

## 🎯 Supervisor Agent

### 役割
Supervisor Agent は、すべてのユーザーインタラクションのメインエントリポイントです。会話をオーケストレーションし、AgentCore Gateway 経由で専門エージェントにタスクを委任し、ユーザーの旅程を管理します。

### コア機能

#### 1. 会話オーケストレーション
- ユーザーリクエストを適切な専門エージェントにルーティング
- セッション間で会話コンテキストとメモリを維持
- サブエージェントからのレスポンスをフォーマットしてユーザーに提示
- コンテキスト認識を伴うマルチターン会話を処理

#### 2. 旅程管理
supervisor は2つの主要ツールでユーザーの旅行旅程を直接管理します：

**`save_itinerary(user_id, items)`**
- 完全な旅程を DynamoDB に保存
- 旅程アイテムの JSON 配列を受け入れ
- 複数のアイテムタイプをサポート：flight、hotel、activity、restaurant、transport
- タイトル、場所、価格、日付、日数、説明などの詳細を保存
- トラベルアシスタントが完全な旅行計画を作成した後に使用

**例：**
```json
[
  {
    "type": "flight",
    "title": "JFK から LAX",
    "price": "$350",
    "date": "2025-12-25",
    "day": 1
  },
  {
    "type": "hotel",
    "title": "Marriott Downtown",
    "location": "ロサンゼルス",
    "price": "$200/泊",
    "date": "2025-12-25",
    "day": 1
  },
  {
    "type": "activity",
    "title": "ハリウッドツアー",
    "location": "ロサンゼルス",
    "price": "$45",
    "date": "2025-12-26",
    "day": 2,
    "description": "ハリウッドのランドマークのガイド付きツアー"
  }
]
```

**`clear_itinerary(user_id)`**
- ユーザーのすべての旅程アイテムを削除
- ユーザーがやり直したい場合や保存されたプランをクリアする場合に使用
- 削除されたアイテムの数を返す

#### 3. Gateway 通信
- AgentCore Gateway 経由で専門エージェントと通信
- ユーザーコンテキスト（user_id、session_id）をすべてのサブエージェントに渡す
- サブエージェントからのストリーミングレスポンスを処理
- 分散サービス間でのツール呼び出しを管理

### 連携の仕組み
1. ユーザーが Supervisor にメッセージを送信
2. Supervisor が意図を分析し、Gateway 経由で適切なエージェントにルーティング
3. 専門エージェントがリクエストを処理し結果を返す
4. Supervisor がレスポンスをフォーマットしてユーザーに提示
5. 旅程が作成された場合、Supervisor が `save_itinerary` を使用して保存

---

## ✈️ Travel Assistant

### 役割
Travel Assistant は、目的地調査、天気情報、フライトとホテルの検索、およびローカルのおすすめを含むすべての旅行関連クエリに特化しています。

### ツールと機能

#### 1. 天気情報
**`get_weather(query)`**
- 任意の都市の5日間の天気予報を取得
- ファジー都市マッチング付き OpenWeather API を使用
- 温度、状態、説明を含む日別予報を提供
- 「パリの天気は？」などの自然言語クエリを処理

**出力例：**
```
1日目 (2025-12-25): 45°F、曇り - 穏やかな気温と薄い雲
2日目 (2025-12-26): 42°F、雨 - 一日中雨が予想されます
...
```

#### 2. インターネット検索
**`search_tool(query)`**
- Tavily API を使用してウェブ検索を実行
- タイトル、コンテンツ、ソースを含むフォーマットされた結果を返す
- 目的地調査、旅行のヒント、最新情報に役立つ
- クエリごとに最大5件の関連結果を提供

**ユースケース：**
- 「東京のベストレストラン」
- 「バルセロナでやるべきこと」
- 「イタリアへの渡航要件」

#### 3. ローカルプレイス検索
**`google_places_tool(query)`**
- ローカルビジネスやアトラクションの Google Places API を検索
- 評価、住所、写真を含む詳細な場所情報を返す
- 特定の会場、レストラン、アトラクションを見つけるのに最適
- 解析しやすい構造化データを提供

**ユースケース：**
- 「エッフェル塔近くのコーヒーショップ」
- 「ローマの美術館」
- 「シアトルダウンタウンのホテル」

#### 4. フライト検索
**`get_flight_offers_tool(origin, destination, departure_date, adults, max_price, currency)`**
- Amadeus API でフライトオファーを検索
- 価格、乗客数、通貨でフィルタリング
- 航空会社、時刻、価格を含むフライト詳細を返す
- IATA 空港コードをサポート（例：JFK、LAX、LHR）

**パラメータ：**
- `origin`: 出発空港コード（例：「BOS」）
- `destination`: 到着空港コード（例：「PAR」）
- `departure_date`: YYYY-MM-DD 形式の日付
- `adults`: 乗客数（デフォルト：1）
- `max_price`: 最大価格フィルター（デフォルト：400）
- `currency`: 通貨コード（デフォルト：「USD」）

#### 5. ホテル検索
**`get_hotel_data_tool(city_code, ratings, amenities, max_price)`**
- Amadeus API で都市内のホテルを検索
- 星評価、アメニティ、価格でフィルタリング
- 名前、場所、価格を含むホテル詳細を返す
- 都市コードをサポート（例：NYC、PAR、ROM）

**パラメータ：**
- `city_code`: 都市コード（例：「NYC」、「PAR」）
- `ratings`: フィルタリングする星評価（例：4-5つ星の場合「4,5」）
- `amenities`: 必要なアメニティ（例：「SWIMMING_POOL」、「SPA」）
- `max_price`: 1泊あたりの最大価格（デフォルト：500）

### ワークフロー例

**ユーザー：** 「12月にパリへの3日間の旅行を計画して」

1. **天気チェック**：Travel Assistant が `get_weather("Paris")` を使用して状況を確認
2. **フライト検索**：`get_flight_offers_tool()` を使用してフライトを検索
3. **ホテル検索**：`get_hotel_data_tool("PAR")` を使用して宿泊施設を検索
4. **ローカル調査**：`search_tool()` と `google_places_tool()` を使用してアトラクションを検索
5. **旅程作成**：すべての情報を構造化された旅程にコンパイル
6. **Supervisor への引き渡し**：完全な旅程を Supervisor に返す
7. **保存**：Supervisor が `save_itinerary()` を呼び出してプランを永続化

---

## 🛒 Cart Manager

### 役割
Cart Manager は、すべてのショッピングカート操作、決済処理、購入フローを処理します。安全な決済トークン化のために Visa と統合し、完全なチェックアウト体験を管理します。

### ツールと機能

#### 1. カート表示
**`get_cart(user_id)`**
- ユーザーのショッピングカート内のすべてのアイテムを取得
- 完全な詳細付きで製品、ホテル、フライトを返す
- 表示しやすいようにタイプ別にアイテムをグループ化
- 価格、日付、予約情報を含む

**返り値：**
```json
[
  {
    "item_type": "hotel",
    "title": "Marriott Downtown",
    "price": "$200",
    "details": {
      "hotel_id": "HLNYC123",
      "city_code": "NYC",
      "rating": "5"
    }
  }
]
```

#### 2. カートへのアイテム追加

**`add_to_cart(user_id, items)`**
- 一般製品をカートに追加
- ASIN、タイトル、価格、およびオプションのレビュー/URL が必要
- ショッピングアイテムと一般的な購入に使用

**`add_hotel_to_cart(user_id, hotels)`**
- Amadeus API からホテルをカートに追加
- hotel_id、city_code、rating、amenities を保存
- 価格を正規化（「/night」接尾辞を削除）
- 旅行旅程にリンク

**`add_flight_to_cart(user_id, flights)`**
- Amadeus API からフライトをカートに追加
- flight_id、origin、destination、departure_date、airline を保存
- 予約用のフライト固有の詳細を追跡
- 旅行旅程にリンク

**例 - ホテルの追加：**
```json
{
  "hotel_id": "HLNYC123",
  "title": "Grand Hotel NYC",
  "price": "$250/night",
  "city_code": "NYC",
  "rating": "5",
  "amenities": "WIFI,POOL,GYM"
}
```

#### 3. アイテムの削除
**`remove_from_cart(user_id, identifiers, item_type)`**
- 識別子（ASIN、hotel_id、または flight_id）でアイテムを削除
- 複数アイテムの一括削除をサポート
- アイテムタイプを検証：'product'、'hotel'、または 'flight'
- 削除されたアイテムの数を返す

#### 4. 日付更新
**`update_itinerary_date(user_id, identifier, item_type, new_date)`**
- フライトの出発日またはホテルのチェックイン日を更新
- 日付形式（YYYY-MM-DD）を検証
- カート内の一致するすべてのアイテムを更新
- 成功ステータスと更新されたアイテムの数を返す

**ユースケース：**
ユーザーがフライトを12月25日から12月27日に変更したい場合：
```python
update_itinerary_date(
    user_id="user-123",
    identifier="FL123456",
    item_type="flight",
    new_date="2025-12-27"
)
```

#### 5. 購入フロー

**ステップ 1：確認のリクエスト**
**`request_purchase_confirmation(user_id)`**
- 合計金額を含む購入サマリーを準備
- ユーザーの支払いカード情報を取得
- すべてのカートアイテムから合計を計算
- ユーザー確認が必要なサマリーを返す

**返り値：**
```json
{
  "requires_confirmation": true,
  "total_amount": 850.00,
  "total_items": 3,
  "payment_method": "Visa 下4桁 1234",
  "message": "3アイテム、$850.00 で購入準備完了..."
}
```

**ステップ 2：購入の確認**
**`confirm_purchase(user_id)`**
- ユーザー確認後に購入を実行
- Visa トークン化経由で決済を処理
- 一意の注文 ID を生成
- 購入成功後にカートをクリア
- 注文確認を返す

**返り値：**
```json
{
  "success": true,
  "order_id": "ORD-20251225-ABC123",
  "total_amount": 850.00,
  "items_count": 3,
  "payment_method": "Visa 下4桁 1234",
  "message": "購入が完了しました！"
}
```

**ステップ 3：確認メールの送信**
**`send_purchase_confirmation_email(order_id, recipient_email, total_amount, items_count, payment_method)`**
- AWS SES 経由で購入確認を送信
- 注文詳細と領収書を含む
- プロフェッショナルな HTML メールテンプレート
- 追跡用のメッセージ ID を返す

#### 6. 支払いカード管理

**`onboard_card(user_id, card_number, expiration_date, cvv, card_type, is_primary)`**
- 新しい支払いカードを安全にオンボード
- Visa トークン化と統合
- 暗号化されたトークンをユーザープロファイルに保存
- プライマリカードとバックアップカードをサポート
- 将来のトランザクション用に vProvisionedTokenId を返す

**セキュリティ機能：**
- カード番号は Visa 経由でトークン化
- 下4桁のみ保存
- CVV は永続化されない
- 暗号化されたトークンを決済に使用

**`get_visa_iframe_config(user_id)`**
- Visa iframe 統合用の設定を提供
- セキュアな iframe URL と設定を返す
- カードオンボーディングフロー用に UI で使用
- PCI コンプライアンスを確保

---

## 🔄 エージェントの連携

### 例：完全な旅行予約フロー

**ユーザーリクエスト：** 「クリスマスにニューヨークへの3日間の旅行を予約したい」

#### フェーズ 1：計画（Supervisor → Travel Assistant）
1. **Supervisor** がリクエストを受信し、Gateway 経由で Travel Assistant にルーティング
2. **Travel Assistant** が実行：
   - `get_weather("New York")` - 12月の天気を確認
   - `get_flight_offers_tool("BOS", "NYC", "2025-12-25")` - フライトを検索
   - `get_hotel_data_tool("NYC", "4,5")` - ホテルを検索
   - `google_places_tool("attractions in New York")` - アクティビティを検索
3. **Travel Assistant** が完全な3日間の旅程をコンパイル
4. **Supervisor** が旅程を受信し、`save_itinerary()` を呼び出して永続化

#### フェーズ 2：予約（Supervisor → Cart Manager）
5. ユーザーが言う：「Marriott ホテルと朝のフライトをカートに追加して」
6. **Supervisor** が Gateway 経由で Cart Manager にルーティング
7. **Cart Manager** が実行：
   - `add_hotel_to_cart()` - 選択したホテルを追加
   - `add_flight_to_cart()` - 選択したフライトを追加
8. **Supervisor** がアイテム追加を確認

#### フェーズ 3：変更（Supervisor → Cart Manager）
9. ユーザーが言う：「やっぱりフライトを12月26日に変更して」
10. **Cart Manager** が実行：
    - `update_itinerary_date("FL123", "flight", "2025-12-26")`
11. **Supervisor** が日付更新を確認

#### フェーズ 4：購入（Supervisor → Cart Manager）
12. ユーザーが言う：「購入する準備ができました」
13. **Cart Manager** が実行：
    - `request_purchase_confirmation()` - サマリーを表示
14. **Supervisor** がサマリーをユーザーに提示
15. ユーザーが購入を確認
16. **Cart Manager** が実行：
    - `confirm_purchase()` - 決済を処理
    - `send_purchase_confirmation_email()` - 領収書を送信
17. **Supervisor** が購入成功を確認

---

## 🔑 主要統合ポイント

### 1. ユーザーコンテキストフロー
- **Supervisor** が user_id と session_id を維持
- すべてのツール呼び出しにパーソナライゼーション用の user_id を含む
- セッションコンテキストがエージェント境界を越えて保持
- メモリが AgentCore Memory サービス経由で共有

### 2. データ引き渡し
- **Travel Assistant** → **Supervisor**：構造化された旅程データ
- **Supervisor** → **Cart Manager**：予約用の選択されたアイテム
- **Cart Manager** → **Supervisor**：購入確認
- すべてのデータが一貫性のために Supervisor を通じて流れる

### 3. エラー処理
- 各エージェントが入力を検証し、構造化されたエラーを返す
- Supervisor がエラーを適切に処理し、ユーザーに通知
- 失敗した操作がカートや旅程の状態を破損しない
- 一時的な障害に対するリトライロジック

### 4. 状態管理
- **旅程**：Supervisor 経由で DynamoDB に保存
- **カート**：Cart Manager 経由で DynamoDB に保存
- **ユーザープロファイル**：DynamoDB に保存（支払いカード、設定）
- **会話**：AgentCore Memory に保存

---

## 🎯 ベストプラクティス

### 旅行計画用：
1. 日程を提案する前に常に天気を確認
2. より良い調整のためにフライトとホテルを一緒に検索
3. 特定の会場の推奨には `google_places_tool` を使用
4. 計画後に `save_itinerary()` で完全な旅程を保存
5. コンテキストのために旅程アイテムに説明を含める

### カート管理用：
1. ユーザーが選択したらアイテムをカートに追加
2. 確定前に `request_purchase_confirmation()` を使用
3. 購入成功後は常に確認メールを送信
4. 日付変更には `update_itinerary_date()` を使用
5. 購入成功後のみカートをクリア

### Supervisor オーケストレーション用：
1. リクエストを適切な専門エージェントにルーティング
2. エージェント呼び出し間で会話コンテキストを維持
3. ユーザーフレンドリーな表示のためにサブエージェントレスポンスをフォーマット
4. 重要なデータ（旅程）を即座に保存
5. 役立つメッセージでエラーを適切に処理

---

## 📊 ツールサマリー

| エージェント | ツール数 | 主要機能 |
|-------|-----------|-------------------|
| **Supervisor** | 2 | 旅程管理、オーケストレーション |
| **Travel Assistant** | 5 | 検索、天気、フライト、ホテル、プレイス |
| **Cart Manager** | 11 | カート操作、決済、購入 |

**合計ツール**：18の専門ツールが連携して包括的な旅行とショッピング支援を提供。

---

## 🚀 アーキテクチャの利点

### マイクロサービス設計
- 各エージェントが独立してデプロイ可能
- エージェントが需要に応じてスケール
- 障害が特定のサービスに分離
- 新しい専門エージェントの追加が容易

### Gateway 通信
- 集中化されたルーティングと認証
- すべてのエージェントで一貫した API
- 組み込みのモニタリングとトレーシング
- セキュアなエージェント間通信

### 関心の分離
- **Supervisor**：会話と調整
- **Travel Assistant**：旅行のドメイン専門知識
- **Cart Manager**：コマースのドメイン専門知識
- 各エージェントが専門分野に集中

このアーキテクチャにより、責任の明確な分離を維持しながら複雑なマルチステップワークフローを処理できる、強力でスケーラブルで保守可能な旅行コンシェルジュシステムが実現します。
