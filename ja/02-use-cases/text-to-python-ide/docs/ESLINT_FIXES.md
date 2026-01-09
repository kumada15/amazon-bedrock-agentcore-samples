# ESLint エラー修正

## よくある ESLint エラーと解決策

### 1. `'ComponentName' is not defined`（react/jsx-no-undef）

**エラー例:**
```
ERROR
[eslint]
src/components/ExecutionResults.js
  Line 67:20:  'Badge' is not defined  react/jsx-no-undef
```

**解決策:**
不足しているコンポーネントをインポート文に追加:

```javascript
// 修正前（Badge が不足）
import {
  Container,
  Header,
  SpaceBetween,
  Box,
  Button
} from '@cloudscape-design/components';

// 修正後（Badge を追加）
import {
  Container,
  Header,
  SpaceBetween,
  Box,
  Button,
  Badge
} from '@cloudscape-design/components';
```

### 2. 未使用変数の警告

**エラー例:**
```
WARNING
[eslint]
src/components/CodeDisplay.js
  Line 2:35:  'SpaceBetween' is defined but never used  no-unused-vars
```

**解決策:**
未使用のインポートを削除:

```javascript
// 修正前（SpaceBetween が未使用）
import { Box, Button, SpaceBetween } from '@cloudscape-design/components';

// 修正後（SpaceBetween を削除）
import { Box, Button } from '@cloudscape-design/components';
```

### 3. コンソール文の警告

**エラー例:**
```
WARNING
[eslint]
src/App.js
  Line 45:7:  Unexpected console statement  no-console
```

**解決策:**
本番用にコンソール文を削除するか、eslint-disable を使用:

```javascript
// オプション 1: コンソール文を削除
// console.log('Debug info'); // これを削除

// オプション 2: 特定の行で eslint を無効化
// eslint-disable-next-line no-console
console.log('Debug info');

// オプション 3: 本番環境では適切なログを使用
if (process.env.NODE_ENV === 'development') {
  console.log('Debug info');
}
```

## よく使用される Cloudscape コンポーネント

以下はインポートが必要な最もよく使用される Cloudscape コンポーネントです:

```javascript
import {
  // レイアウト
  AppLayout,
  ContentLayout,
  Container,
  Header,
  Box,
  SpaceBetween,
  ColumnLayout,

  // フォームコントロール
  Button,
  Input,
  Textarea,
  FormField,
  FileUpload,
  Select,

  // フィードバック
  Alert,
  Spinner,
  StatusIndicator,
  Badge,

  // ナビゲーション
  Tabs,
  Modal,
  Link,

  // データ表示
  Table,
  CodeEditor
} from '@cloudscape-design/components';
```

## クイック修正コマンド

### ESLint チェックを実行
```bash
cd frontend
npm run lint
```

### ESLint 問題を自動修正
```bash
cd frontend
npx eslint src/ --fix
```

### 特定のファイルをチェック
```bash
cd frontend
npx eslint src/components/ExecutionResults.js
```

## 予防のヒント

1. **IDE 拡張機能を使用:** IDE 用の ESLint 拡張機能をインストール
2. **Pre-commit フック:** コミット前に ESLint を実行するよう設定
3. **定期的なチェック:** 開発中に定期的に `npm run lint` を実行
4. **インポートの整理:** インポートを整理し、未使用のものを削除

## フロントエンドのテスト

フロントエンドテストスクリプトを実行して一般的な問題をチェック:

```bash
node test_frontend.js
```

以下をチェックします:
- 不足しているファイル
- 不足している依存関係
- インポートの問題
- 非推奨のコンポーネント使用
