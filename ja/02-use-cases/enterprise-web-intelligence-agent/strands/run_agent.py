#!/usr/bin/env python3
"""Strands フレームワークで競合インテリジェンスエージェントを実行する。"""

import asyncio
import os
import sys
from pathlib import Path
from typing import Dict, List, TypedDict, Annotated, Optional, Any

# Add parent directory to path
parent_dir = str(Path(__file__).parent.parent)
sys.path.append(parent_dir)


from utils.imports import setup_interactive_tools_import
paths = setup_interactive_tools_import()

from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.panel import Panel

from shared.utils.s3_datasource import UnifiedS3DataSource

from config import AgentConfig
from agent import CompetitiveIntelligenceAgent
from interactive_tools.live_view_sessionreplay.session_replay_viewer import SessionReplayViewer

#from ..shared.utils.s3_datasource import UnifiedS3DataSource
#from ..shared.utils.imports import setup_interactive_tools_import

console = Console()


def get_bedrock_agentcore_single() -> List[Dict]:
    """AWS Bedrock AgentCore の価格を分析する。"""
    return [
        {
            "name": "AWS Bedrock AgentCore",
            "url": "https://aws.amazon.com/bedrock/agentcore/pricing/"
        }
    ]


def get_bedrock_vs_vertex() -> List[Dict]:
    """AWS Bedrock AgentCore と Google Vertex AI を比較する。"""
    return [
        {
            "name": "AWS Bedrock AgentCore",
            "url": "https://aws.amazon.com/bedrock/agentcore/pricing/"
        },
        {
            "name": "Google Vertex AI",
            "url": "https://cloud.google.com/vertex-ai/pricing"
        }
    ]


def get_custom_competitors() -> List[Dict]:
    """明示的な分析オプション付きでユーザー入力からカスタム競合を取得する。"""
    competitors = []
    
    console.print("\n[bold]分析する競合を入力してください:[/bold]")
    console.print("[dim]終了するには空の名前で Enter を押してください[/dim]\n")
    
    while True:
        name = Prompt.ask("競合企業名", default="")
        if not name:
            break

        url = Prompt.ask(f"{name} の URL")
        
        # Let user specify what to analyze
        console.print("\n[cyan]何を分析しますか?[/cyan]")
        console.print("1. 価格情報")
        console.print("2. 製品機能")
        console.print("3. API ドキュメント")
        console.print("4. 会社/概要情報")
        console.print("5. 上記すべて")
        
        analysis_choice = Prompt.ask(
            "オプションを選択 (カンマ区切り、例: 1,2,3)",
            default="1,2"
        )
        
        analyze = []
        if "1" in analysis_choice:
            analyze.extend(["pricing", "tiers"])
        if "2" in analysis_choice:
            analyze.extend(["features", "capabilities"])
        if "3" in analysis_choice:
            analyze.extend(["api", "docs", "developer"])
        if "4" in analysis_choice:
            analyze.extend(["about", "company", "team"])
        if "5" in analysis_choice:
            analyze = ["pricing", "tiers", "features", "capabilities", 
                      "api", "docs", "about", "company"]
        
        # Ask for specific URLs (optional)
        additional_urls = {}
        if Confirm.ask("価格/ドキュメントページの特定の URL がありますか?", default=False):
            if "pricing" in analyze:
                pricing_url = Prompt.ask("価格ページの URL (任意)", default="")
                if pricing_url:
                    additional_urls["pricing_url"] = pricing_url
            if "api" in analyze or "docs" in analyze:
                docs_url = Prompt.ask("API/ドキュメント URL (任意)", default="")
                if docs_url:
                    additional_urls["docs_url"] = docs_url
        
        competitors.append({
            "name": name,
            "url": url,
            "analyze": analyze,
            "additional_urls": additional_urls,
            "auto_discover": True
        })
        
        console.print(f"[green]✓ {name} を追加しました - 分析項目: {', '.join(analyze)}[/green]\n")
    
    return competitors


def show_competitors_table(competitors: List[Dict]):
    """競合をテーブル形式で表示する。"""
    table = Table(title="分析対象の競合", title_style="bold cyan")
    table.add_column("#", style="cyan", width=4)
    table.add_column("名前", style="magenta")
    table.add_column("URL", style="blue")
    
    for i, comp in enumerate(competitors, 1):
        table.add_row(
            str(i),
            comp['name'],
            comp['url'][:50] + "..." if len(comp['url']) > 50 else comp['url']
        )
    
    console.print(table)


async def view_replay(recording_config: Any, config: AgentConfig):
    """
    録画設定を使用してセッションリプレイビューアを起動する。

    Args:
        recording_config: S3Location を含む dict または文字列パス
        config: エージェント設定
    """
    try:
        console.print("\n[cyan]🎭 Starting session replay viewer...[/cyan]")
        
        # Handle both structured config and legacy string format
        if isinstance(recording_config, dict):
            # New structured format from API
            if 's3Location' in recording_config:
                s3_location = recording_config['s3Location']
                bucket = s3_location.get('bucket')
                prefix = s3_location.get('prefix', '').rstrip('/')
            else:
                # Direct dict with bucket and prefix
                bucket = recording_config.get('bucket')
                prefix = recording_config.get('prefix', '').rstrip('/')
            
            # Extract session ID from prefix
            prefix_parts = prefix.split('/')
            session_id = prefix_parts[-1] if prefix_parts else 'unknown'
            
        elif isinstance(recording_config, str):
            # Legacy string format (s3://bucket/prefix/session_id/)
            console.print("[yellow]⚠️ Using legacy S3 path format[/yellow]")
            parts = recording_config.replace("s3://", "").rstrip("/").split("/")
            bucket = parts[0]
            prefix = "/".join(parts[1:-1]) if len(parts) > 2 else ""
            session_id = parts[-1] if len(parts) > 1 else "unknown"
        else:
            raise ValueError(f"Invalid recording configuration format: {type(recording_config)}")
        
        console.print(f"[dim]バケット: {bucket}[/dim]")
        console.print(f"[dim]プレフィックス: {prefix}[/dim]")
        console.print(f"[dim]セッション: {session_id}[/dim]")
        
        # Wait for recordings to be uploaded
        console.print("⏳ 録画が S3 にアップロードされるのを待機中 (30秒)...")
        await asyncio.sleep(30)
        
        # Use the unified S3 data source
        data_source = UnifiedS3DataSource(
            bucket=bucket,
            prefix=prefix,
            session_id=session_id
        )
        
        # Start replay viewer
        console.print(f"🎬 セッションリプレイビューアを開始: {session_id}")
        viewer = SessionReplayViewer(
            data_source=data_source,
            port=config.replay_viewer_port
        )
        viewer.start()
        
    except Exception as e:
        console.print(f"[red]❌ リプレイビューアの開始エラー: {e}[/red]")
        import traceback
        traceback.print_exc()


async def main():
    """エージェントを実行するメイン関数。"""
    console.print(Panel(
        "[bold cyan]🎯 Competitive Intelligence Agent[/bold cyan]\n\n"
        "[bold]Powered by Strands Framework & Amazon Bedrock[/bold]\n\n"
        "Migration from LangGraph → Strands ✅\n\n"
        "All Features Preserved:\n"
        "• 🔍 Automated browser navigation with CDP\n"
        "• 📊 Intelligent content extraction with LLM\n"
        "• 📸 Screenshot capture with annotations\n"
        "• 📹 Full session recording to S3\n"
        "• 🎭 Session replay capability\n"
        "• 🤖 Claude 3.5 Sonnet for analysis\n"
        "• ⚡ Parallel processing support\n"
        "• 💾 Session persistence & resume\n"
        "• ☁️ AWS CLI integration\n"
        "• 📝 Advanced form analysis\n"
        "• 🌐 Multi-page workflows",
        title="Welcome - Strands Edition",
        border_style="blue"
    ))
    
    # Load configuration
    config = AgentConfig()
    
    # Validate configuration
    if not config.validate():
        console.print("[red]❌ Configuration validation failed[/red]")
        console.print("必要な環境変数を設定してください")
        return
    
    # Show configuration
    console.print("\n[bold]設定:[/bold]")
    console.print(f"  リージョン: {config.region}")
    console.print(f"  モデル: {config.llm_model_id}")
    console.print(f"  S3 バケット: {config.s3_bucket}")
    console.print(f"  ロール ARN: {config.recording_role_arn}")
    console.print()
    
    # Check for resume option
    resume_session = None
    if Confirm.ask("以前のセッションを再開しますか?", default=False):
        resume_session = Prompt.ask("再開するセッション ID を入力")
    
    # Get competitors
    console.print("\n[bold]分析オプションを選択:[/bold]")
    console.print("1. 🎯 AWS Bedrock AgentCore 価格のみ")
    console.print("2. 🆚 Bedrock AgentCore と Vertex AI を比較")
    console.print("3. ✏️  カスタム競合")

    choice = Prompt.ask("オプションを選択", choices=["1", "2", "3"], default="1")
    
    if choice == "1":
        competitors = get_bedrock_agentcore_single()
    elif choice == "2":
        competitors = get_bedrock_vs_vertex()
    else:
        competitors = get_custom_competitors()
        if not competitors:
            console.print("[yellow]競合が入力されませんでした。終了します。[/yellow]")
            return
    
    # Show competitors
    show_competitors_table(competitors)
    
    # Ask for processing mode
    parallel_mode = False
    if len(competitors) > 1:
        parallel_mode = Confirm.ask(
            f"\n⚡ {len(competitors)} 件の競合に対して並列処理を使用しますか?",
            default=False
        )

    if not Confirm.ask("\n分析を続行しますか?", default=True):
        console.print("[yellow]分析がキャンセルされました。[/yellow]")
        return

    # Create and run agent
    agent = CompetitiveIntelligenceAgent(config)

    try:
        # Initialize with optional session resume
        await agent.initialize(resume_session_id=resume_session)
        
        # Show what to watch for
        watch_panel = Panel(
            "[bold yellow]👁️  Watch the Live Browser Viewer![/bold yellow]\n\n"
            "[bold]The browser will automatically:[/bold]\n"
            "• Navigate to each competitor's pricing page\n"
            "• Scroll through pages to discover content\n"
            "• Extract pricing information and features\n"
            "• Take annotated screenshots\n"
            "• Generate a comprehensive report\n\n"
            f"[bold]Mode:[/bold] {'⚡ Parallel' if parallel_mode else '🔄 Sequential'}\n\n"
            "[dim]Framework: Strands (migrated from LangGraph)[/dim]",
            border_style="yellow"
        )
        console.print(watch_panel)
        
        console.print("\n[cyan]5秒後に自動分析を開始します...[/cyan]")
        await asyncio.sleep(5)
        
        # Run analysis
        results = await agent.run(competitors, parallel=parallel_mode)
        
        if results["success"]:
            # Show results summary
            results_panel = Panel(
                f"[bold green]✅ Analysis Complete![/bold green]\n\n"
                f"[bold]Key Findings:[/bold]\n"
                f"📊 Competitors analyzed: {len(competitors)}\n"
                f"🌐 API endpoints discovered: {len(results.get('apis_discovered', []))}\n"
                f"📄 Report generated: Yes\n"
                f"📹 Session recorded: Yes\n"
                f"💾 Session ID: {results.get('session_id', 'N/A')}\n"
                f"⚡ Processing mode: {'Parallel' if parallel_mode else 'Sequential'}\n\n"
                f"[dim]Framework: Strands[/dim]",
                border_style="green"
            )
            console.print(results_panel)
            
            # Show report preview
            if results.get("report"):
                console.print("\n[bold]レポートプレビュー:[/bold]")
                console.print("-" * 60)
                preview = results['report'][:1500]
                console.print(preview + "..." if len(results['report']) > 1500 else preview)
                console.print("-" * 60)
            
            # Ask about replay
            #if results.get("recording_path"):
            #    if Confirm.ask("\nView session replay?", default=True):
            #        await view_replay(results["recording_path"], config)
                    #
            if results.get("recording_config") or results.get("recording_path"):
                replay_prompt = Panel(
                    "[bold cyan]🎬 Session Recording Available![/bold cyan]\n\n"
                    "Your entire analysis session has been recorded.\n"
                    "You can replay it to:\n"
                    "• Review the extraction process\n"
                    "• Share findings with stakeholders\n"
                    "• Debug any issues\n"
                    "• Create training materials",
                    border_style="cyan"
                )
                console.print(replay_prompt)
                
                if Confirm.ask("\nセッションリプレイを表示しますか?", default=True):
                    # Use recording_config if available, fallback to recording_path
                    recording_data = results.get("recording_config") or results.get("recording_path")
                    await view_replay(recording_data, config)
        else:
            console.print(f"\n[red]分析に失敗しました: {results.get('error', '不明なエラー')}[/red]")
    
    except KeyboardInterrupt:
        console.print("\n[yellow]ユーザーによって分析が中断されました[/yellow]")
    except Exception as e:
        console.print(f"\n[red]予期しないエラー: {e}[/red]")
        import traceback
        traceback.print_exc()
    finally:
        await agent.cleanup()
        console.print("\n[green]✅ エージェントのシャットダウンが完了しました[/green]")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[yellow]ユーザーによって中断されました[/yellow]")
    except Exception as e:
        console.print(f"\n[red]予期しないエラー: {e}[/red]")
        import traceback
        traceback.print_exc()