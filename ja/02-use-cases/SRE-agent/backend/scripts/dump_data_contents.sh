#!/bin/bash
# dump_data_contents.sh - Recursively display all files in the data folder with paths and contents

# Get the script directory and navigate to backend
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"
DATA_DIR="$BACKEND_DIR/data"

# データディレクトリが存在するか確認
if [ ! -d "$DATA_DIR" ]; then
    echo "エラー: データディレクトリが見つかりません: $DATA_DIR"
    exit 1
fi

# ヘッダー
echo "=============================================="
echo "データディレクトリ内容ダンプ"
echo "生成日時: $(date)"
echo "データディレクトリ: $DATA_DIR"
echo "=============================================="
echo

# ファイル内容をフォーマット付きで出力する関数
print_file_contents() {
    local file="$1"
    local relative_path="${file#$DATA_DIR/}"

    echo "=================================================="
    echo "ファイル: data/$relative_path"
    echo "=================================================="

    # バイナリファイルかどうか確認
    if file "$file" | grep -q "text"; then
        # テキストファイル - 内容を表示
        cat "$file"
    else
        # バイナリファイル - ファイル情報のみ表示
        echo "[バイナリファイル - $(file "$file")]"
        echo "[サイズ: $(ls -lh "$file" | awk '{print $5}')]"
    fi

    echo
    echo
}

# 処理対象のすべてのファイルを検索してリスト表示
echo "処理対象ファイル:"
echo "================="
find "$DATA_DIR" -type f -name "*.json" -o -type f -name "*.txt" -o -type f -name "*.log" | grep -v "all_data_dump.txt" | sort | while read -r file; do
    relative_path="${file#$DATA_DIR/}"
    echo "  - data/$relative_path"
done
echo
echo

# すべてのファイルを再帰的に検索して処理（all_data_dump.txt を除く）
find "$DATA_DIR" -type f -name "*.json" -o -type f -name "*.txt" -o -type f -name "*.log" | grep -v "all_data_dump.txt" | sort | while read -r file; do
    relative_path="${file#$DATA_DIR/}"
    echo "処理中: data/$relative_path" >&2
    print_file_contents "$file"
done

# 最後にサマリーを表示
echo "=============================================="
echo "サマリー"
echo "=============================================="
echo "合計ファイル数 (all_data_dump.txt を除く): $(find "$DATA_DIR" -type f | grep -v "all_data_dump.txt" | wc -l)"
echo "合計ディレクトリ数: $(find "$DATA_DIR" -type d | wc -l)"
echo "合計サイズ: $(du -sh "$DATA_DIR" | cut -f1)"
echo

# Default output file
OUTPUT_FILE="$DATA_DIR/all_data_dump.txt"

# 直接実行された場合（ソースされたりパイプされていない場合）
if [ "$0" = "${BASH_SOURCE[0]}" ] && [ -t 1 ]; then
    echo "データダンプを生成中: $OUTPUT_FILE"
    # スクリプトを再度実行し、出力をファイルにリダイレクト
    "$0" > "$OUTPUT_FILE" 2>&1
    echo "データダンプが完了しました。出力は次のファイルに保存されました: $OUTPUT_FILE"
    echo "ファイルサイズ: $(ls -lh "$OUTPUT_FILE" | awk '{print $5}')"
fi