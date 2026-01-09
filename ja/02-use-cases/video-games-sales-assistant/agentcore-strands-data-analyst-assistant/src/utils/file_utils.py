def load_file_content(file_path: str, default_content: str = None) -> str:
    """
    オプションのフォールバックと包括的なエラーハンドリングを備えてファイル内容を読み込む。

    Args:
        file_path (str): 読み取るファイルのパス
        default_content (str, optional): ファイルが見つからない場合のフォールバック内容

    Returns:
        str: ファイル内容、または提供されている場合はデフォルト内容

    Raises:
        FileNotFoundError: ファイルが見つからず、デフォルトが提供されていない場合
        Exception: その他のファイル読み取りエラー（詳細メッセージ付き）
    """
    try:
        with open(file_path, "r") as file:
            return file.read()
    except FileNotFoundError:
        if default_content is not None:
            return default_content
        else:
            raise FileNotFoundError(f"File not found: {file_path}")
    except Exception as e:
        raise Exception(f"Error reading file {file_path}: {str(e)}")
