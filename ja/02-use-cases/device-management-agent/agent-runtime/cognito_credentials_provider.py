#!/usr/bin/python
"""
Amazon Cognito OAuth2 認証情報プロバイダー管理 CLI

このモジュールは、Amazon Bedrock AgentCore における Amazon Cognito OAuth2
認証情報プロバイダーを管理するためのコマンドラインインターフェースを提供します。
エージェント認証に使用される OAuth2 認証情報プロバイダーの作成、削除、
および一覧表示を可能にします。

この CLI ツールは、OAuth2 認証の設定プロセスを自動化します：
- Cognito 設定で認証情報プロバイダーを作成
- プロバイダー情報を .env ファイルに保存して簡単にアクセス
- プロバイダーのライフサイクル管理（作成、削除、一覧表示）
- 必須環境変数の検証

主な機能:
    - カスタム名で OAuth2 認証情報プロバイダーを作成
    - プロバイダー永続化のための自動 .env ファイル管理
    - 既存の全認証情報プロバイダーを一覧表示
    - 確認プロンプト付きで認証情報プロバイダーを削除
    - 環境変数の検証とエラーハンドリング

コマンド:
    create: 新しい Cognito OAuth2 認証情報プロバイダーを作成
    delete: 既存の認証情報プロバイダーを削除
    list: 全ての OAuth2 認証情報プロバイダーを一覧表示

必須環境変数:
    COGNITO_CLIENT_ID: Amazon Cognito アプリクライアント ID
    COGNITO_CLIENT_SECRET: Amazon Cognito アプリクライアントシークレット
    COGNITO_DISCOVERY_URL: OIDC ディスカバリー URL/発行者
    COGNITO_AUTH_URL: 認可エンドポイント URL
    COGNITO_TOKEN_URL: トークンエンドポイント URL
    AWS_REGION: AgentCore 操作用の AWS リージョン

管理される環境変数:
    COGNITO_PROVIDER_NAME: 作成された認証情報プロバイダーの名前

使用例:
    新しいプロバイダーを作成:
    >>> python cognito_credentials_provider.py create --name my-provider

    全てのプロバイダーを一覧表示:
    >>> python cognito_credentials_provider.py list

    プロバイダーを削除:
    >>> python cognito_credentials_provider.py delete --name my-provider

    自動確認付きで削除:
    >>> python cognito_credentials_provider.py delete --name my-provider --confirm

注意事項:
    - プロバイダー名は参照しやすいように .env ファイルに保存されます
    - 削除には --confirm フラグがない限り確認が必要です
    - 全ての操作には有効な AWS 認証情報が必要です
"""
import boto3
import click
import sys
import os
from dotenv import load_dotenv
from utils import get_aws_region

# Load environment variables from .env file
load_dotenv()

REGION = get_aws_region()

identity_client = boto3.client(
    "bedrock-agentcore-control",
    region_name=REGION,
)


def get_env_variable(var_name: str, description: str = None) -> str:
    """検証付きで環境変数を取得します。"""
    value = os.getenv(var_name)
    if not value:
        desc = description or var_name
        click.echo(f"❌ 必須環境変数が不足しています: {var_name}", err=True)
        click.echo(f"   .env ファイルに {desc} を設定してください", err=True)
        sys.exit(1)
    return value


def store_provider_name_in_env(provider_name: str):
    """認証情報プロバイダー名を .env ファイルに保存します。"""
    env_file_path = ".env"
    try:
        # Read existing .env file content
        env_lines = []
        if os.path.exists(env_file_path):
            with open(env_file_path, 'r', encoding='utf-8') as f:
                env_lines = f.readlines()
        
        # Remove existing COGNITO_PROVIDER_NAME if it exists
        env_lines = [line for line in env_lines if not line.startswith('COGNITO_PROVIDER_NAME=')]
        
        # Add the new provider name
        env_lines.append(f"COGNITO_PROVIDER_NAME={provider_name}\n")
        
        # Write back to .env file
        with open(env_file_path, 'w', encoding='utf-8') as f:
            f.writelines(env_lines)
        
        click.echo(f"📦 プロバイダー名を .env ファイルに保存しました: {provider_name}")
    except Exception as e:
        click.echo(f"⚠️ プロバイダー名の .env ファイルへの保存に失敗しました: {e}")


def get_provider_name_from_env() -> str:
    """認証情報プロバイダー名を .env ファイルから取得します。"""
    return os.getenv("COGNITO_PROVIDER_NAME")


def delete_provider_name_from_env():
    """.env ファイルからプロバイダー名を削除します。"""
    env_file_path = ".env"
    try:
        if not os.path.exists(env_file_path):
            return
        
        # Read existing .env file content
        with open(env_file_path, 'r', encoding='utf-8') as f:
            env_lines = f.readlines()
        
        # Remove COGNITO_PROVIDER_NAME line
        env_lines = [line for line in env_lines if not line.startswith('COGNITO_PROVIDER_NAME=')]
        
        # Write back to .env file
        with open(env_file_path, 'w', encoding='utf-8') as f:
            f.writelines(env_lines)
        
        click.echo("🧹 .env ファイルからプロバイダー名を削除しました")
    except Exception as e:
        click.echo(f"⚠️ .env ファイルからのプロバイダー名の削除に失敗しました: {e}")


def create_cognito_provider(provider_name: str) -> dict:
    """Cognito OAuth2 認証情報プロバイダーを作成します。"""
    try:
        click.echo("📥 環境変数から Cognito 設定を読み込み中...")

        client_id = get_env_variable("COGNITO_CLIENT_ID", "Cognito アプリクライアント ID")
        click.echo(f"✅ クライアント ID を取得しました: {client_id}")

        client_secret = get_env_variable("COGNITO_CLIENT_SECRET", "Cognito アプリクライアントシークレット")
        click.echo(f"✅ クライアントシークレットを取得しました: {client_secret[:4]}***")

        issuer = get_env_variable("COGNITO_DISCOVERY_URL", "OIDC ディスカバリー URL/発行者")
        auth_url = get_env_variable("COGNITO_AUTH_URL", "認可エンドポイント URL")
        token_url = get_env_variable("COGNITO_TOKEN_URL", "トークンエンドポイント URL")

        click.echo(f"✅ 発行者: {issuer}")
        click.echo(f"✅ 認可エンドポイント: {auth_url}")
        click.echo(f"✅ トークンエンドポイント: {token_url}")

        click.echo("⚙️  OAuth2 認証情報プロバイダーを作成中...")
        cognito_provider = identity_client.create_oauth2_credential_provider(
            name=provider_name,
            credentialProviderVendor="CustomOauth2",
            oauth2ProviderConfigInput={
                "customOauth2ProviderConfig": {
                    "clientId": client_id,
                    "clientSecret": client_secret,
                    "oauthDiscovery": {
                        "authorizationServerMetadata": {
                            "issuer": issuer,
                            "authorizationEndpoint": auth_url,
                            "tokenEndpoint": token_url,
                            "responseTypes": ["code", "token"],
                        }
                    },
                }
            },
        )

        click.echo("✅ OAuth2 認証情報プロバイダーを正常に作成しました")
        provider_arn = cognito_provider["credentialProviderArn"]
        click.echo(f"   プロバイダー ARN: {provider_arn}")
        click.echo(f"   プロバイダー名: {cognito_provider['name']}")

        # Store provider name in .env file
        store_provider_name_in_env(provider_name)

        return cognito_provider

    except Exception as e:
        click.echo(f"❌ Cognito 認証情報プロバイダーの作成エラー: {str(e)}", err=True)
        sys.exit(1)


def delete_cognito_provider(provider_name: str) -> bool:
    """Cognito OAuth2 認証情報プロバイダーを削除します。"""
    try:
        click.echo(f"🗑️  OAuth2 認証情報プロバイダーを削除中: {provider_name}")

        identity_client.delete_oauth2_credential_provider(name=provider_name)

        click.echo("✅ OAuth2 認証情報プロバイダーを正常に削除しました")
        return True

    except Exception as e:
        click.echo(f"❌ 認証情報プロバイダーの削除エラー: {str(e)}", err=True)
        return False


def list_credential_providers() -> list:
    """全ての OAuth2 認証情報プロバイダーを一覧表示します。"""
    try:
        response = identity_client.list_oauth2_credential_providers(maxResults=20)
        providers = response.get("credentialProviders", [])
        return providers

    except Exception as e:
        click.echo(f"❌ 認証情報プロバイダーの一覧取得エラー: {str(e)}", err=True)
        return []


def find_provider_by_name(provider_name: str) -> bool:
    """名前でプロバイダーが存在するか確認します。"""
    providers = list_credential_providers()
    for provider in providers:
        if provider.get("name") == provider_name:
            return True
    return False


@click.group()
@click.pass_context
def cli(ctx):
    """AgentCore Cognito 認証情報プロバイダー管理 CLI。

    Cognito 認証用の OAuth2 認証情報プロバイダーを作成および削除します。
    """
    ctx.ensure_object(dict)


@cli.command()
@click.option(
    "--name", required=True, help="認証情報プロバイダーの名前（必須）"
)
def create(name):
    """新しい Cognito OAuth2 認証情報プロバイダーを作成します。"""
    click.echo(f"🚀 Cognito 認証情報プロバイダーを作成中: {name}")
    click.echo(f"📍 リージョン: {REGION}")

    # Check if provider already exists in .env
    existing_name = get_provider_name_from_env()
    if existing_name:
        click.echo(f"⚠️  .env ファイルにプロバイダーが既に存在します: {existing_name}")
        if not click.confirm("置き換えますか？"):
            click.echo("❌ 操作がキャンセルされました")
            sys.exit(0)

    try:
        provider = create_cognito_provider(provider_name=name)
        click.echo("🎉 Cognito 認証情報プロバイダーを正常に作成しました！")
        click.echo(f"   プロバイダー ARN: {provider['credentialProviderArn']}")
        click.echo(f"   プロバイダー名: {provider['name']}")

    except Exception as e:
        click.echo(f"❌ 認証情報プロバイダーの作成に失敗しました: {str(e)}", err=True)
        sys.exit(1)


@cli.command()
@click.option(
    "--name",
    help="削除する認証情報プロバイダーの名前（指定しない場合は .env ファイルから読み取ります）",
)
@click.option("--confirm", is_flag=True, help="確認プロンプトをスキップ")
def delete(name, confirm):
    """Cognito OAuth2 認証情報プロバイダーを削除します。"""

    # If no name provided, try to get from .env file
    if not name:
        name = get_provider_name_from_env()
        if not name:
            click.echo(
                "❌ プロバイダー名が指定されておらず、.env ファイルから読み取れませんでした",
                err=True,
            )
            click.echo("   ヒント: 'list' コマンドで利用可能なプロバイダーを確認してください")
            sys.exit(1)
        click.echo(f"📖 .env ファイルのプロバイダー名を使用: {name}")

    click.echo(f"🔍 認証情報プロバイダーを検索中: {name}")

    # Check if provider exists
    if not find_provider_by_name(name):
        click.echo(f"❌ 指定された名前の認証情報プロバイダーが見つかりません: {name}", err=True)
        click.echo("   ヒント: 'list' コマンドで利用可能なプロバイダーを確認してください")
        sys.exit(1)

    click.echo(f"📖 プロバイダーが見つかりました: {name}")

    # Confirmation prompt
    if not confirm:
        if not click.confirm(
            f"⚠️  認証情報プロバイダー '{name}' を削除してもよろしいですか？この操作は元に戻せません。"
        ):
            click.echo("❌ 操作がキャンセルされました")
            sys.exit(0)

    if delete_cognito_provider(name):
        click.echo(f"✅ 認証情報プロバイダー '{name}' を正常に削除しました")

        # Remove provider name from .env file
        delete_provider_name_from_env()
        click.echo("🎉 認証情報プロバイダーを削除し、.env ファイルから正常に削除しました")
    else:
        click.echo("❌ 認証情報プロバイダーの削除に失敗しました", err=True)
        sys.exit(1)


@cli.command("list")
def list_providers():
    """全ての OAuth2 認証情報プロバイダーを一覧表示します。"""
    providers = list_credential_providers()

    if not providers:
        click.echo("ℹ️  認証情報プロバイダーが見つかりません")
        return

    click.echo(f"📋 {len(providers)} 件の認証情報プロバイダーが見つかりました:")
    for provider in providers:
        click.echo(f"  • 名前: {provider.get('name', 'N/A')}")
        click.echo(f"    ARN: {provider['credentialProviderArn']}")
        click.echo(f"    ベンダー: {provider.get('credentialProviderVendor', 'N/A')}")
        if "createdTime" in provider:
            click.echo(f"    作成日時: {provider['createdTime']}")
        click.echo()


if __name__ == "__main__":
    cli()
