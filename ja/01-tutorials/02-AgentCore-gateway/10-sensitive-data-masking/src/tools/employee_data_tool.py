"""
従業員データツール - Gateway 用のモック従業員情報 API

このツールは連絡先や所在地の PII を含むモック従業員情報を提供します。
警告: このツールは機密 PII データを扱うため、アクセスを制限する必要があります。
"""

import json
import random
from datetime import datetime


def lambda_handler(event, context):
    """
    Lambda handler for employee data tool.

    Expected input:
    {
        "employee_id": "EMP-98765"
    }

    Returns mock employee data including PII (email, address).
    """
    print(f"Employee data tool received event: {json.dumps(event)}")

    # 入力をパース
    body = event if isinstance(event, dict) else json.loads(event)
    employee_id = body.get('employee_id', None)

    if not employee_id:
        return {
            "statusCode": 400,
            "body": json.dumps({
                "tool": "employee_data_tool",
                "error": "employee_id is required",
                "success": False
            })
        }

    # モック従業員データを生成
    # フィールド名は機密性を示さないが、コンテンツには PII が含まれる
    first_names = ['Alice', 'Bob', 'Carol', 'David', 'Emma', 'Frank', 'Grace', 'Henry']
    last_names = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis']
    departments = ['Engineering', 'Marketing', 'Sales', 'Operations', 'Finance', 'Human Resources']
    cities = ['Boston', 'Seattle', 'Austin', 'Denver', 'Portland', 'Chicago']
    streets = ['Oak Avenue', 'Maple Street', 'Pine Road', 'Elm Drive', 'Cedar Lane', 'Birch Way']
    
    first_name = random.choice(first_names)
    last_name = random.choice(last_names)
    department = random.choice(departments)
    city = random.choice(cities)
    street = random.choice(streets)
    
    # 従業員データを生成（5フィールド: 2つが機密、3つが非機密）
    employee_data = {
        # 非機密: ビジネス識別子
        "employee_id": employee_id,

        # 非機密: 組織情報
        "department": department,

        # 機密: メールアドレスを含む（フィールド名は示さない）
        # EMAIL - Guardrails によって検出され匿名化される
        "contact_info": f"{first_name.lower()}.{last_name.lower()}@company.com",

        # 機密: 住所を含む（フィールド名は直接示さない）
        # ADDRESS - フィールド名ではなくコンテンツに基づいて Guardrails によって検出され匿名化される
        "mailing_info": f"{random.randint(100, 9999)} {street}, {city}, MA {random.randint(10000, 99999)}",

        # 非機密: 雇用状況
        "status": random.choice(['Active', 'On Leave', 'Remote']),

        "financial_info": {
            # 機密 - Guardrails によってマスクされる
            # US_BANK_ACCOUNT_NUMBER - Guardrails によって検出される
            "bank_account": f"{random.randint(100000000, 999999999)}",

            # US_BANK_ROUTING_NUMBER - Guardrails によって検出される
            "routing_number": f"{random.randint(100000000, 999999999)}",

            # CREDIT_DEBIT_CARD_NUMBER - Guardrails によって検出される
            "credit_card": f"{random.randint(4000, 4999)}-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}",

            # CREDIT_DEBIT_CARD_CVV - Guardrails によって検出される
            "cvv": f"{random.randint(100, 999)}",

            # CREDIT_DEBIT_CARD_EXPIRY - Guardrails によって検出される
            "card_expiry": f"{random.randint(1, 12):02d}/{random.randint(25, 30)}",

            # PIN - Guardrails によって検出される
            "pin": f"{random.randint(1000, 9999)}",

            # US_INDIVIDUAL_TAX_IDENTIFICATION_NUMBER - Guardrails によって検出される
            "tax_id": f"{random.randint(900, 999)}-{random.randint(70, 99)}-{random.randint(1000, 9999)}",

            # 非機密 - これらはマスクされない
            "account_balance": round(random.uniform(1000, 50000), 2),
            "credit_score": random.randint(600, 850),
            "currency": "USD",
            "payment_terms": random.choice(['Net 30', 'Net 60', 'Immediate']),
            "credit_limit": round(random.uniform(5000, 50000), 2),
            "available_credit": round(random.uniform(1000, 25000), 2)
        },
    }

    response = {
        "statusCode": 200,
        "body": {
            "tool": "employee_data_tool",
            "result": employee_data,
            "success": True,
            "note": "Sensitive fields (contact_info, mailing_info) will be anonymized by Bedrock Guardrails based on content, not field names."
        }
    }

    print(f"Employee data tool response generated")
    return response


# Gateway 登録用の MCP ツール定義
TOOL_DEFINITION = {
    "name": "employee_data_tool",
    "description": "Retrieve employee information by Employee ID. Returns employee record with contact and location information. Sensitive data will be automatically anonymized by Bedrock Guardrails.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "employee_id": {
                "type": "string",
                "description": "The unique employee identifier (e.g., 'EMP-98765')"
            }
        },
        "required": ["employee_id"]
    }
}


if __name__ == "__main__":
    # ローカルでツールをテスト
    test_events = [
        {"employee_id": "EMP-98765"},
        {"employee_id": "EMP-12345"},
        {}  # Test missing employee_id
    ]

    for test_event in test_events:
        print(f"\n{'='*60}")
        print(f"Testing with: {test_event}")
        print(f"{'='*60}")
        result = lambda_handler(test_event, None)
        print(f"\nTest result:\n{json.dumps(result, indent=2)}")
