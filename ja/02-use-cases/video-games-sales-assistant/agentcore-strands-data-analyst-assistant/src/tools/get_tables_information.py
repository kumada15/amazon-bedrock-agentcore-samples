from strands import tool
from src.utils import load_file_content


@tool
def get_tables_information() -> dict:
    """
    ユーザーの質問に回答するための SQL クエリを生成するために利用可能なデータテーブルに関する情報を提供する。

    Returns:
        dict: 'toolUsed' と 'information' をキーに持つテーブル情報を含む辞書

    Note:
        カレントディレクトリに 'tables_information.txt' という名前のファイルが存在することを期待します。
        ファイルが見つからない場合は、辞書内にエラーメッセージを返します。
    """
    try:
        return {
            "toolUsed": "get_tables_information",
            "information": load_file_content("src/tools/tables_information.txt"),
        }
    except FileNotFoundError:
        return {
            "toolUsed": "get_tables_information",
            "information": "エラー: src/tools/tables_information.txt ファイルが見つかりません。テーブル情報を含むこのファイルを作成してください。",
        }
    except Exception as e:
        return {
            "toolUsed": "get_tables_information",
            "information": f"テーブル情報の読み取りエラー: {str(e)}",
        }
