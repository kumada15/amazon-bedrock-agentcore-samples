"""数学演算を実行するための電卓ツール。"""

import logging
import math
from typing import Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s,p%(process)s,{%(filename)s:%(lineno)d},%(levelname)s,%(message)s",
)

logger = logging.getLogger(__name__)


def _add(
    a: float,
    b: float,
) -> float:
    """2 つの数を加算します。

    Args:
        a: 1 番目の数
        b: 2 番目の数

    Returns:
        a と b の和
    """
    return a + b


def _subtract(
    a: float,
    b: float,
) -> float:
    """2 つの数を減算します。

    Args:
        a: 1 番目の数
        b: 2 番目の数

    Returns:
        a と b の差
    """
    return a - b


def _multiply(
    a: float,
    b: float,
) -> float:
    """2 つの数を乗算します。

    Args:
        a: 1 番目の数
        b: 2 番目の数

    Returns:
        a と b の積
    """
    return a * b


def _divide(
    a: float,
    b: float,
) -> float:
    """2 つの数を除算します。

    Args:
        a: 1 番目の数（被除数）
        b: 2 番目の数（除数）

    Returns:
        a を b で割った商

    Raises:
        ValueError: 除数がゼロの場合
    """
    if b == 0:
        logger.error("ゼロ除算が試行されました")
        raise ValueError("Cannot divide by zero")

    return a / b


def _factorial(
    a: float,
) -> int:
    """数の階乗を計算します。

    Args:
        a: 階乗を計算する数

    Returns:
        数の階乗

    Raises:
        ValueError: 数が負または整数でない場合
    """
    if a < 0:
        logger.error(f"負の数の階乗が試行されました: {a}")
        raise ValueError("Cannot calculate factorial of a negative number")

    if not a.is_integer():
        logger.error(f"非整数の階乗が試行されました: {a}")
        raise ValueError("Factorial requires an integer value")

    return math.factorial(int(a))


def calculator(
    operation: str,
    a: float,
    b: float | None = None,
) -> dict[str, Any]:
    """数学計算を実行します。

    Args:
        operation: 実行する数学演算
            （add、subtract、multiply、divide、factorial）
        a: 1 番目の数（または階乗用の数）
        b: 2 番目の数（階乗では使用しない）

    Returns:
        演算、入力、結果を含む辞書

    Raises:
        ValueError: 演算または入力が無効な場合
    """
    if not operation or not isinstance(operation, str):
        logger.error(f"無効な操作パラメータ: {operation}")
        raise ValueError("Operation must be a non-empty string")

    operation_normalized = operation.strip().lower()

    valid_operations = ["add", "subtract", "multiply", "divide", "factorial"]
    if operation_normalized not in valid_operations:
        logger.error(f"不明な操作: {operation_normalized}")
        raise ValueError(
            f"Unknown operation: {operation}. Valid operations are: {', '.join(valid_operations)}"
        )

    if not isinstance(a, (int, float)):
        logger.error(f"無効な第1引数: {a}")
        raise ValueError("First number must be a numeric value")

    logger.info(f"{operation_normalized} 演算を実行中: a={a}, b={b}")

    result_value: float

    if operation_normalized == "add":
        if b is None:
            raise ValueError("Addition requires two numbers")
        result_value = _add(a, b)

    elif operation_normalized == "subtract":
        if b is None:
            raise ValueError("Subtraction requires two numbers")
        result_value = _subtract(a, b)

    elif operation_normalized == "multiply":
        if b is None:
            raise ValueError("Multiplication requires two numbers")
        result_value = _multiply(a, b)

    elif operation_normalized == "divide":
        if b is None:
            raise ValueError("Division requires two numbers")
        result_value = _divide(a, b)

    elif operation_normalized == "factorial":
        result_value = _factorial(a)

    result = {
        "operation": operation_normalized,
        "input_a": a,
        "input_b": b if b is not None else None,
        "result": result_value,
    }

    logger.info(f"計算結果: {result_value}")

    return result
