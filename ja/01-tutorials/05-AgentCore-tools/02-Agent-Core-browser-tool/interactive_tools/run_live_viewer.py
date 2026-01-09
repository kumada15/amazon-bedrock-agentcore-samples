#!/usr/bin/env python3
"""
Bedrock-AgentCore Browser Live Viewer を実行するためのスタンドアロンスクリプト。
interactive_tools モジュールの使用方法を示します。
"""


import time
from pathlib import Path


from rich.console import Console
from rich.panel import Panel
from bedrock_agentcore.tools.browser_client import BrowserClient
from .browser_viewer import BrowserViewerServer

console = Console()

def main():
    """ディスプレイサイズ設定付きでブラウザライブビューアーを実行します。"""
    console.print(Panel(
        "[bold cyan]Bedrock-AgentCore Browser Live Viewer[/bold cyan]\n\n"
        "This demonstrates:\n"
        "• Live browser viewing with DCV\n"
        "• Configurable display sizes (not limited to 900×800)\n"
        "• Proper display layout callbacks\n\n"
        "[yellow]Note: Requires Amazon DCV SDK files[/yellow]",
        title="Browser Live Viewer",
        border_style="blue"
    ))
    
    try:
        # ステップ 1: ブラウザセッションを作成
        console.print("\n[cyan]Step 1: Creating browser session...[/cyan]")
        browser_client = BrowserClient(region="us-west-2")
        session_id = browser_client.start()
        console.print(f"✅ Session created: {session_id}")
        
        # ステップ 2: ビューアーサーバーを起動
        console.print("\n[cyan]Step 2: Starting viewer server...[/cyan]")
        viewer = BrowserViewerServer(browser_client, port=8000)
        viewer_url = viewer.start(open_browser=True)
        
        # ステップ 3: 機能を表示
        console.print("\n[bold green]Viewer Features:[/bold green]")
        console.print("• Default display: 1600×900 (configured via displayLayout callback)")
        console.print("• Size options: 720p, 900p, 1080p, 1440p")
        console.print("• Real-time display updates")
        console.print("• Take/Release control functionality")
        
        console.print("\n[yellow]Press Ctrl+C to stop[/yellow]")
        
        # 実行を継続
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        console.print("\n\n[yellow]Shutting down...[/yellow]")
        if 'browser_client' in locals():
            browser_client.stop()
            console.print("✅ Browser session terminated")
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
