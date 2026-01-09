#!/usr/bin/python
import boto3
import click
import sys
from botocore.exceptions import ClientError
from utils import get_ssm_parameter, get_aws_region

REGION = get_aws_region()

identity_client = boto3.client(
    "bedrock-agentcore-control",
    region_name=REGION,
)
ssm = boto3.client("ssm", region_name=REGION)


def store_provider_name_in_ssm(provider_name: str):
    """認証情報プロバイダー名を SSM パラメータに保存する。"""
    param_name = "/app/customersupport/agentcore/cognito_provider"
    try:
        ssm.put_parameter(
            Name=param_name, Value=provider_name, Type="String", Overwrite=True
        )
        click.echo(f"🔐 Stored provider name in SSM: {param_name}")
    except ClientError as e:
        click.echo(f"⚠️ Failed to store provider name in SSM: {e}")


def get_provider_name_from_ssm() -> str:
    """SSM パラメータから認証情報プロバイダー名を取得する。"""
    param_name = "/app/customersupport/agentcore/cognito_provider"
    try:
        response = ssm.get_parameter(Name=param_name)
        return response["Parameter"]["Value"]
    except ClientError:
        return None


def delete_ssm_param():
    """プロバイダー用の SSM パラメータを削除する。"""
    param_name = "/app/customersupport/agentcore/cognito_provider"
    try:
        ssm.delete_parameter(Name=param_name)
        click.echo(f"🧹 Deleted SSM parameter: {param_name}")
    except ClientError as e:
        click.echo(f"⚠️ Failed to delete SSM parameter: {e}")


def create_cognito_provider(provider_name: str) -> dict:
    """Cognito OAuth2 認証情報プロバイダーを作成する。"""
    try:
        click.echo("📥 Fetching Cognito configuration from SSM...")
        client_id = get_ssm_parameter(
            "/app/customersupport/agentcore/machine_client_id"
        )
        click.echo(f"✅ Retrieved client ID: {client_id}")

        client_secret = get_ssm_parameter(
            "/app/customersupport/agentcore/cognito_secret"
        )
        click.echo(f"✅ Retrieved client secret: {client_secret[:4]}***")

        issuer = get_ssm_parameter(
            "/app/customersupport/agentcore/cognito_discovery_url"
        )
        auth_url = get_ssm_parameter("/app/customersupport/agentcore/cognito_auth_url")
        token_url = get_ssm_parameter(
            "/app/customersupport/agentcore/cognito_token_url"
        )

        click.echo(f"✅ Issuer: {issuer}")
        click.echo(f"✅ Authorization Endpoint: {auth_url}")
        click.echo(f"✅ Token Endpoint: {token_url}")

        click.echo("⚙️  Creating OAuth2 credential provider...")
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

        click.echo("✅ OAuth2 credential provider created successfully")
        provider_arn = cognito_provider["credentialProviderArn"]
        click.echo(f"   Provider ARN: {provider_arn}")
        click.echo(f"   Provider Name: {cognito_provider['name']}")

        # Store provider name in SSM
        store_provider_name_in_ssm(provider_name)

        return cognito_provider

    except Exception as e:
        click.echo(f"❌ Error creating Cognito credential provider: {str(e)}", err=True)
        sys.exit(1)


def delete_cognito_provider(provider_name: str) -> bool:
    """Cognito OAuth2 認証情報プロバイダーを削除する。"""
    try:
        click.echo(f"🗑️  Deleting OAuth2 credential provider: {provider_name}")

        identity_client.delete_oauth2_credential_provider(name=provider_name)

        click.echo("✅ OAuth2 credential provider deleted successfully")
        return True

    except Exception as e:
        click.echo(f"❌ Error deleting credential provider: {str(e)}", err=True)
        return False


def list_credential_providers() -> list:
    """すべての OAuth2 認証情報プロバイダーを一覧表示する。"""
    try:
        response = identity_client.list_oauth2_credential_providers(maxResults=20)
        providers = response.get("credentialProviders", [])
        return providers

    except Exception as e:
        click.echo(f"❌ Error listing credential providers: {str(e)}", err=True)
        return []


def find_provider_by_name(provider_name: str) -> bool:
    """名前でプロバイダーが存在するか確認する。"""
    providers = list_credential_providers()
    for provider in providers:
        if provider.get("name") == provider_name:
            return True
    return False


@click.group()
@click.pass_context
def cli(ctx):
    """AgentCore Cognito 認証情報プロバイダー管理 CLI。

    Cognito 認証用の OAuth2 認証情報プロバイダーを作成・削除します。
    """
    ctx.ensure_object(dict)


@cli.command()
@click.option(
    "--name", required=True, help="Name for the credential provider (required)"
)
def create(name):
    """新しい Cognito OAuth2 認証情報プロバイダーを作成する。"""
    click.echo(f"🚀 Creating Cognito credential provider: {name}")
    click.echo(f"📍 Region: {REGION}")

    # Check if provider already exists in SSM
    existing_name = get_provider_name_from_ssm()
    if existing_name:
        click.echo(f"⚠️  A provider already exists in SSM: {existing_name}")
        if not click.confirm("Do you want to replace it?"):
            click.echo("❌ Operation cancelled")
            sys.exit(0)

    try:
        provider = create_cognito_provider(provider_name=name)
        click.echo("🎉 Cognito credential provider created successfully!")
        click.echo(f"   Provider ARN: {provider['credentialProviderArn']}")
        click.echo(f"   Provider Name: {provider['name']}")

    except Exception as e:
        click.echo(f"❌ Failed to create credential provider: {str(e)}", err=True)
        sys.exit(1)


@cli.command()
@click.option(
    "--name",
    help="Name of the credential provider to delete (if not provided, will read from SSM parameter)",
)
@click.option("--confirm", is_flag=True, help="Skip confirmation prompt")
def delete(name, confirm):
    """Cognito OAuth2 認証情報プロバイダーを削除する。"""

    # If no name provided, try to get from SSM
    if not name:
        name = get_provider_name_from_ssm()
        if not name:
            click.echo(
                "❌ No provider name provided and couldn't read from SSM parameter",
                err=True,
            )
            click.echo("   Hint: Use 'list' command to see available providers")
            sys.exit(1)
        click.echo(f"📖 Using provider name from SSM: {name}")

    click.echo(f"🔍 Looking for credential provider: {name}")

    # Check if provider exists
    if not find_provider_by_name(name):
        click.echo(f"❌ No credential provider found with name: {name}", err=True)
        click.echo("   Hint: Use 'list' command to see available providers")
        sys.exit(1)

    click.echo(f"📖 Found provider: {name}")

    # Confirmation prompt
    if not confirm:
        if not click.confirm(
            f"⚠️  Are you sure you want to delete credential provider '{name}'? This action cannot be undone."
        ):
            click.echo("❌ Operation cancelled")
            sys.exit(0)

    if delete_cognito_provider(name):
        click.echo(f"✅ Credential provider '{name}' deleted successfully")

        # Always delete SSM parameter
        delete_ssm_param()
        click.echo("🎉 Credential provider and SSM parameter deleted successfully")
    else:
        click.echo("❌ Failed to delete credential provider", err=True)
        sys.exit(1)


@cli.command("list")
def list_providers():
    """すべての OAuth2 認証情報プロバイダーを一覧表示する。"""
    providers = list_credential_providers()

    if not providers:
        click.echo("ℹ️  No credential providers found")
        return

    click.echo(f"📋 Found {len(providers)} credential provider(s):")
    for provider in providers:
        click.echo(f"  • Name: {provider.get('name', 'N/A')}")
        click.echo(f"    ARN: {provider['credentialProviderArn']}")
        click.echo(f"    Vendor: {provider.get('credentialProviderVendor', 'N/A')}")
        if "createdTime" in provider:
            click.echo(f"    Created: {provider['createdTime']}")
        click.echo()


if __name__ == "__main__":
    cli()
