from fastmcp import FastMCP
from fastmcp.server.middleware import Middleware, MiddlewareContext
import boto3
import logging
from botocore.config import Config
from opentelemetry import trace

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure boto3 with 30-second timeouts
boto_config = Config(
    connect_timeout=30, read_timeout=30, retries={"max_attempts": 3, "mode": "adaptive"}
)

# Initialize AWS clients with timeouts
ssm = boto3.client("ssm", config=boto_config)
dynamodb = boto3.resource("dynamodb", config=boto_config)

tracer = trace.get_tracer("customer_support_vpc_mcp", "1.0.0")


# OpenTelemetry Middleware
class OpenTelemetryMiddleware(Middleware):
    """OpenTelemetry ですべてのツール呼び出しを自動的にトレースするミドルウェア"""

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        # Access tool info from the message
        tool_name = getattr(context.message, "name", "unknown_tool")
        tool_args = getattr(context.message, "arguments", {})

        with tracer.start_as_current_span(f"tool.{tool_name}") as span:
            # Set standard attributes
            span.set_attribute("tool.name", tool_name)
            span.set_attribute("mcp.method", context.method)

            # Set tool-specific attributes
            if isinstance(tool_args, dict):
                for key, value in tool_args.items():
                    span.set_attribute(f"tool.args.{key}", str(value))

            try:
                # Execute the tool
                result = await call_next(context)

                # Mark success
                span.set_attribute("result.success", True)

                return result
            except Exception as e:
                # Mark error
                span.set_attribute("error", True)
                span.set_attribute("error.type", type(e).__name__)
                span.set_attribute("error.message", str(e))
                span.set_attribute("result.success", False)
                raise


def get_table_names():
    """
    SSM パラメータから DynamoDB テーブル名を取得する
    """
    # Get both table names from SSM parameters
    response = ssm.get_parameters(
        Names=[
            "/app/customersupportvpc/dynamodb/reviews_table_name",
            "/app/customersupportvpc/dynamodb/products_table_name",
        ]
    )

    table_names = {}
    for param in response["Parameters"]:
        if "reviews" in param["Name"]:
            table_names["reviews"] = param["Value"]
            logger.info(f"レビューテーブル名を取得しました: {param['Value']}")
        elif "products" in param["Name"]:
            table_names["products"] = param["Value"]
            logger.info(f"製品テーブル名を取得しました: {param['Value']}")

    return table_names


# Get table names dynamically
table_names = get_table_names()

# Reference the tables using dynamic names
reviews_table = dynamodb.Table(table_names["reviews"])
products_table = dynamodb.Table(table_names["products"])

logger.info(
    f"DynamoDB テーブルを初期化しました: reviews={table_names['reviews']}, products={table_names['products']}"
)

# Initialize FastMCP
mcp = FastMCP()

# Add OpenTelemetry middleware
mcp.add_middleware(OpenTelemetryMiddleware())


@mcp.tool
def get_reviews(review_id: str):
    """
    review_id で単一のレビューを取得する
    """
    try:
        logger.info(f"レビューを取得中 ID: {review_id}")
        response = reviews_table.get_item(Key={"review_id": review_id})
        item = response.get("Item")
        if not item:
            logger.warning(f"レビューが見つかりません: {review_id}")
            return {"error": "Review not found"}
        logger.info(f"レビューを正常に取得しました: {review_id}")
        return item
    except Exception as e:
        logger.error(f"レビュー {review_id} の取得中にエラーが発生しました: {str(e)}")
        return {"error": str(e)}


@mcp.tool
def get_products(product_id: int):
    """
    product_id で単一の製品を取得する
    """
    try:
        logger.info(f"製品を取得中 ID: {product_id}")
        response = products_table.get_item(Key={"product_id": product_id})
        item = response.get("Item")
        if not item:
            logger.warning(f"製品が見つかりません: {product_id}")
            return {"error": "Product not found"}
        logger.info(f"製品を正常に取得しました: {product_id}")
        return item
    except Exception as e:
        logger.error(f"製品 {product_id} の取得中にエラーが発生しました: {str(e)}")
        return {"error": str(e)}


# @mcp.tool
# def get_todo(todo_id: int):
#     """
#     Fetch a single todo by todo_id
#     """
#     return todo_id


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", stateless_http=True)
