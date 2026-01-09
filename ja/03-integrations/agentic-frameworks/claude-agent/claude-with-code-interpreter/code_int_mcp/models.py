"""Code Interpreterのデータモデル。"""

from pydantic import BaseModel, Field
from typing import Optional


class CodeIntExecutionResult(BaseModel):
    """コード実行の結果モデル。"""

    output: str
    code_int_session_id: str
    execution_time: float = Field(..., ge=0, description="Execution time in seconds")
    success: bool
    error: Optional[str] = None
