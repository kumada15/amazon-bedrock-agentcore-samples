"""競合インテリジェンス収集用のメイン Strands エージェント。"""

import asyncio
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import nest_asyncio
import sys

sys.path.insert(0, str(Path(__file__).parent))

from utils.imports import setup_interactive_tools_import
paths = setup_interactive_tools_import()

from strands import Agent, tool
from strands.models import BedrockModel
from strands.session.s3_session_manager import S3SessionManager
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

from interactive_tools.browser_viewer import BrowserViewerServer

# ツールをインポート
from config import AgentConfig
from browser_tools import BrowserTools
from analysis_tools import AnalysisTools

# ネストされたイベントループを許可するために nest_asyncio を適用
nest_asyncio.apply()

console = Console()


class CompetitiveIntelligenceAgent:
    """競合インテリジェンス収集用の Strands エージェント。"""
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self.browser_tools = BrowserTools(config)
        self.analysis_tools = AnalysisTools(config)
        self.agent = None
        self.browser_viewer = None
        self.parallel_browser_sessions = []
        # イベントループを保存
        self.loop = None
    
    def _safe_state_get(self, key: str, default: Any = None) -> Any:
        """デフォルト値付きで安全に状態値を取得する。"""
        try:
            value = self.agent.state.get(key)
            return value if value is not None else default
        except:
            return default
    
    async def initialize(self, resume_session_id: Optional[str] = None):
        """オプションのセッション再開機能付きでエージェントとツールを初期化する。"""
        console.print(Panel(
            "[bold cyan]🎯 Competitive Intelligence Agent[/bold cyan]\n\n"
            "[bold]Powered by Amazon Bedrock and Strands Framework[/bold]\n\n"
            "Features:\n"
            "• 🌐 Automated browser navigation\n"
            "• 📊 Real-time API and network analysis\n"
            "• 🎯 Intelligent content extraction\n"
            "• 📸 Screenshot capture\n"
            "• 📹 Full session recording to S3\n"
            "• 🔄 Multi-tool orchestration\n"
            "• ⚡ Parallel processing support\n",
            title="Initializing",
            border_style="blue"
        ))
        
        # 現在のイベントループを保存
        self.loop = asyncio.get_event_loop()
        
        # 録画付きでブラウザを初期化
        self.browser_tools.create_browser_with_recording()
        
        # 永続化のためのセッションマネージャを設定
        session_manager = None
        if resume_session_id:
            console.print(f"[cyan]🔄 Resuming session: {resume_session_id}[/cyan]")
            session_manager = S3SessionManager(
                session_id=resume_session_id,
                bucket=self.config.s3_bucket,
                prefix=f"{self.config.s3_prefix}sessions/",
                region_name=self.config.region
            )
        
        # Bedrock モデルを初期化
        bedrock_model = BedrockModel(
            model_id=self.config.llm_model_id,
            region_name=self.config.region
        )
        
        # CDP でブラウザセッションを初期化 - 重要: エージェント作成前に実行
        await self.browser_tools.initialize_browser_session(bedrock_model)
        
        # コードインタープリタを初期化
        self.analysis_tools.initialize()
        
        # すべてのツールを持つメイン Strands エージェントを作成
        self.agent = Agent(
            model=bedrock_model,
            system_prompt=self._get_system_prompt(),
            tools=self._create_agent_tools(),
            session_manager=session_manager,
            callback_handler=self._create_callback_handler()
        )
        
        # 新規開始時に状態を初期化
        if not resume_session_id:
            self.agent.state.set("competitors", [])
            self.agent.state.set("current_competitor_index", 0)
            self.agent.state.set("competitor_data", {})
            self.agent.state.set("analysis_results", {})
            self.agent.state.set("total_screenshots", 0)
            self.agent.state.set("discovered_apis", [])
            self.agent.state.set("parallel_mode", False)
        else:
            console.print("[green]✅ Previous session data loaded[/green]")
        
        # ブラウザライブビューアを開始
        if self.browser_tools.browser_client:
            console.print("\n[cyan]🖥️ Starting live browser viewer...[/cyan]")
            self.browser_viewer = BrowserViewerServer(
                self.browser_tools.browser_client, 
                port=self.config.live_view_port
            )
            viewer_url = self.browser_viewer.start(open_browser=True)
            console.print(f"[green]✅ Live viewer: {viewer_url}[/green]")
            console.print("[dim]You can take/release control in the viewer[/dim]")
        
        console.print("\n[green]✅ Agent initialized successfully![/green]")
        console.print(f"[cyan]📹 Recording to: {self.browser_tools.recording_path}[/cyan]")
    
    def _get_system_prompt(self) -> str:
        """エージェント用のシステムプロンプトを取得する。"""
        return """あなたは競合インテリジェンス分析エージェントです。競合分析を依頼された場合：
        1. 各競合企業に対して analyze_website ツールを使用する
        2. 収集したデータを分析するために perform_analysis ツールを使用する
        3. 最終レポートを作成するために generate_report ツールを使用する

        分析を完了するために、常にこれらのツールを順番に使用してください。"""
    
    def _create_agent_tools(self) -> List:
        """すべてのエージェントツールを作成する。"""
        tools = []
        
        # ツールで使用するために self への参照を保存
        agent_instance = self
        
        @tool
        def analyze_website(competitor_name: str, competitor_url: str) -> str:
            """
            競合のウェブサイトを分析して、価格、機能、その他のインテリジェンスを抽出する。

            Args:
                competitor_name: 競合企業の名前
                competitor_url: 分析対象の競合ウェブサイトの URL
            """
            # 既存のイベントループで run_until_complete を使用
            if agent_instance.loop and agent_instance.loop.is_running():
                # 既に非同期コンテキスト内なので、タスクを作成
                future = asyncio.ensure_future(
                    agent_instance._analyze_website_impl(competitor_name, competitor_url),
                    loop=agent_instance.loop
                )
                
                # ネストされたループを処理するために nest_asyncio を使用
                return agent_instance.loop.run_until_complete(future)
            else:
                # 実行中のループがないため、asyncio.run を使用
                return asyncio.run(agent_instance._analyze_website_impl(competitor_name, competitor_url))
        
        @tool
        def perform_analysis() -> str:
            """
            収集したすべての競合データを分析してパターンとインサイトを特定する。
            """
            console.print("\n[bold yellow]📊 Analyzing all competitor data...[/bold yellow]")
            
            competitor_data = agent_instance._safe_state_get("competitor_data", {})
            
            if not competitor_data:
                return "No competitor data to analyze yet"

            # 各競合を分析
            for competitor_name, data in competitor_data.items():
                console.print(f"[cyan]Analyzing {competitor_name}...[/cyan]")
                analysis_result = agent_instance.analysis_tools.analyze_competitor_data(
                    competitor_name, data
                )
                
                # 分析結果を保存
                analysis_results = agent_instance._safe_state_get("analysis_results", {})
                analysis_results[competitor_name] = analysis_result
                agent_instance.agent.state.set("analysis_results", analysis_results)
            
            # ビジュアライゼーションを作成
            console.print("[cyan]Creating comparison visualizations...[/cyan]")
            viz_result = agent_instance.analysis_tools.create_comparison_visualization(competitor_data)
            
            analysis_results = agent_instance._safe_state_get("analysis_results", {})
            analysis_results["visualizations"] = viz_result
            agent_instance.agent.state.set("analysis_results", analysis_results)
            
            return "Analysis completed successfully"
        
        @tool
        def generate_report() -> str:
            """
            分析したデータから最終的な競合インテリジェンスレポートを生成する。
            """
            console.print("\n[bold green]📄 Generating final report...[/bold green]")
            
            competitor_data = agent_instance._safe_state_get("competitor_data", {})
            analysis_results = agent_instance._safe_state_get("analysis_results", {})
            
            if not competitor_data:
                return "No data to generate report from"

            # レポートを生成
            report_result = agent_instance.analysis_tools.generate_final_report(
                competitor_data, analysis_results
            )
            
            agent_instance.agent.state.set("report", report_result.get("report_content", ""))
            agent_instance.agent.state.set("recording_path", agent_instance.browser_tools.recording_path)
            
            return "Report generated successfully"
        
        # ツールをリストに追加
        tools.extend([
            analyze_website,
            perform_analysis,
            generate_report
        ])
        
        return tools
    
    async def _analyze_website_impl(self, competitor_name: str, competitor_url: str) -> str:
        """ウェブサイト分析の実装。"""
        console.print(f"\n[bold blue]🔍 Analyzing: {competitor_name}[/bold blue]")
        console.print(f"[cyan]URL: {competitor_url}[/cyan]")
        
        competitor_data = {}
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            console=console
        ) as progress:
            task = progress.add_task(f"Analyzing {competitor_name}...", total=10)
            
            try:
                # ウェブサイトに移動
                progress.update(task, description="Navigating to website...", advance=1)
                nav_result = await self.browser_tools.navigate_to_url(competitor_url)
                competitor_data['navigation'] = nav_result
                
                if nav_result.get('status') != 'success':
                    console.print(f"[yellow]⚠️ Navigation failed: {nav_result.get('error')}[/yellow]")
                    # データを取得するためにとりあえず続行
                
                # スクリーンショットを撮影
                progress.update(task, description="Taking homepage screenshot...", advance=1)
                await self.browser_tools.take_annotated_screenshot(f"{competitor_name} - Homepage")
                
                # セクションを検出
                progress.update(task, description="Discovering page sections...", advance=1)
                discovered_sections = await self.browser_tools.intelligent_scroll_and_discover()
                competitor_data['discovered_sections'] = discovered_sections
                console.print(f"[green]Found {len(discovered_sections)} key sections[/green]")
                
                # 価格ページを探す
                progress.update(task, description="Looking for pricing page...", advance=1)
                found_pricing = await self.browser_tools.smart_navigation("pricing")
                if found_pricing:
                    await asyncio.sleep(3)
                    await self.browser_tools.take_annotated_screenshot(f"{competitor_name} - Pricing")
                
                # フォームを分析
                progress.update(task, description="Checking interactive elements...", advance=1)
                form_data = await self.browser_tools.analyze_forms_and_inputs()
                competitor_data['interactive_elements'] = form_data
                
                # 価格を抽出
                progress.update(task, description="Extracting pricing...", advance=1)
                pricing_result = await self.browser_tools.extract_pricing_info()
                competitor_data['pricing'] = pricing_result
                
                # 機能を抽出
                progress.update(task, description="Extracting features...", advance=1)
                features_result = await self.browser_tools.extract_product_features()
                competitor_data['features'] = features_result
                
                # 追加ページを探索
                progress.update(task, description="Exploring additional pages...", advance=1)
                additional_pages = await self.browser_tools.explore_multi_page_workflow(
                    ["features", "docs", "api", "about"]
                )
                competitor_data['additional_pages'] = additional_pages
                
                # メトリクスをキャプチャ
                progress.update(task, description="Capturing metrics...", advance=1)
                metrics = await self.browser_tools.capture_performance_metrics()
                competitor_data['performance_metrics'] = metrics
                
                # 状態に保存
                progress.update(task, description="Saving data...", advance=1)
                all_competitor_data = self._safe_state_get("competitor_data", {})
                all_competitor_data[competitor_name] = {
                    "url": competitor_url,
                    "timestamp": datetime.now().isoformat(),
                    **competitor_data,
                    "status": "success"
                }
                self.agent.state.set("competitor_data", all_competitor_data)
                
                # 状態のメトリクスを更新
                total_screenshots = self._safe_state_get("total_screenshots", 0)
                self.agent.state.set("total_screenshots", total_screenshots + len(self.browser_tools._screenshots_taken))
                
                discovered_apis = self._safe_state_get("discovered_apis", [])
                discovered_apis.extend(self.browser_tools._discovered_apis)
                self.agent.state.set("discovered_apis", discovered_apis)
                
            except Exception as e:
                console.print(f"[red]❌ Error analyzing {competitor_name}: {e}[/red]")
                import traceback
                traceback.print_exc()
                
                competitor_data = {"status": "error", "error": str(e)}
                
                all_competitor_data = self._safe_state_get("competitor_data", {})
                all_competitor_data[competitor_name] = competitor_data
                self.agent.state.set("competitor_data", all_competitor_data)
                
                return f"Error analyzing {competitor_name}: {str(e)}"
        
        console.print(f"[green]✅ Completed: {competitor_name}[/green]")
        return f"Successfully analyzed {competitor_name} - found {len(discovered_sections)} sections, extracted pricing and features"
    
    def _create_callback_handler(self):
        """進捗追跡用のコールバックハンドラを作成する。"""
        def callback_handler(**kwargs):
            # ツール使用を追跡
            if "current_tool_use" in kwargs and kwargs["current_tool_use"].get("name"):
                tool_name = kwargs["current_tool_use"]["name"]
                console.print(f"[cyan]🔧 Using tool: {tool_name}[/cyan]")
            
            # テキスト出力を表示
            if "data" in kwargs:
                # LLM の完全な推論は出力せず、ツール呼び出しのみ
                pass
        
        return callback_handler
    

    async def run(self, competitors: List[Dict], parallel: bool = False) -> Dict:
        """競合インテリジェンス分析を実行する。"""
        try:
            # 競合を状態に保存
            self.agent.state.set("competitors", competitors)
            
            console.print("\n[cyan]🤖 Starting competitive analysis workflow...[/cyan]")
            console.print(f"[bold]Analyzing {len(competitors)} competitors[/bold]")
            
            # 各競合を順次分析
            for i, competitor in enumerate(competitors, 1):
                console.print(f"\n[bold yellow]📊 Competitor {i}/{len(competitors)}: {competitor['name']}[/bold yellow]")
                
                try:
                    # ツールを直接呼び出し
                    result = self.agent.tool.analyze_website(
                        competitor_name=competitor['name'],
                        competitor_url=competitor['url']
                    )
                    console.print(f"[green]✓ {competitor['name']} analysis complete[/green]")
                    console.print(f"[dim]Result: {result[:200]}...[/dim]" if len(result) > 200 else f"[dim]Result: {result}[/dim]")
                    
                    # 過負荷を避けるために競合間に少し遅延を追加
                    if i < len(competitors):
                        console.print(f"[dim]Waiting 2 seconds before next competitor...[/dim]")
                        await asyncio.sleep(2)
                        
                except Exception as comp_error:
                    console.print(f"[red]❌ Error analyzing {competitor['name']}: {comp_error}[/red]")
                    # 一つが失敗しても次の競合に進む
                    continue
            
            console.print("\n[bold cyan]All competitors analyzed, generating insights...[/bold cyan]")
            
            # 分析を実行
            console.print("\n[yellow]Running data analysis...[/yellow]")
            try:
                analysis_result = self.agent.tool.perform_analysis()
                console.print(f"[green]✓ Analysis complete[/green]")
            except Exception as e:
                console.print(f"[red]Analysis error: {e}[/red]")
                analysis_result = "Analysis failed"
            
            # レポートを生成
            console.print("\n[yellow]Generating report...[/yellow]")
            try:
                report_result = self.agent.tool.generate_report()
                console.print(f"[green]✓ Report generated[/green]")
            except Exception as e:
                console.print(f"[red]Report generation error: {e}[/red]")
                report_result = "Report generation failed"
            
            # 最終状態を取得
            report = self._safe_state_get("report")
            recording_path = self._safe_state_get("recording_path") or self.browser_tools.recording_path
            analysis_results = self._safe_state_get("analysis_results", {})
            apis_discovered = self._safe_state_get("discovered_apis", [])
            total_screenshots = self._safe_state_get("total_screenshots", 0)
            competitor_data = self._safe_state_get("competitor_data", {})
            
            # サマリーを表示
            console.print("\n" + "="*60)
            console.print(Panel(
                f"[bold green]✅ Analysis Complete![/bold green]\n\n"
                f"📊 Competitors requested: {len(competitors)}\n"
                f"✓ Successfully analyzed: {len([c for c in competitor_data.values() if c.get('status') == 'success'])}\n"
                f"✗ Failed: {len([c for c in competitor_data.values() if c.get('status') == 'error'])}\n"
                f"📸 Screenshots taken: {total_screenshots}\n"
                f"🔍 APIs discovered: {len(apis_discovered)}\n"
                f"📄 Report generated: {'Yes' if report else 'No'}\n"
                f"📹 Recording: {recording_path}\n\n"
                f"[bold]Analyzed:[/bold]\n" + 
                "\n".join([f"  • {name}: {data.get('status', 'unknown')}" 
                        for name, data in competitor_data.items()]),
                title="Summary",
                border_style="green"
            ))
            console.print("="*60)
            
            return {
                "success": True,
                "report": self._safe_state_get("report"),
                "recording_path": self.browser_tools.recording_path if self.browser_tools else None,
                "recording_config": self.browser_tools.recording_config if self.browser_tools else None,  # NEW
                "analysis_results": self._safe_state_get("analysis_results", {}),
                "apis_discovered": self._safe_state_get("discovered_apis", []),
                "session_id": datetime.now().strftime("%Y%m%d_%H%M%S"),
                "parallel_mode": self._safe_state_get("parallel_mode", False)
            }
            
        except Exception as e:
            console.print(f"[red]❌ Agent error: {e}[/red]")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}
    
    async def cleanup(self):
        """エージェントのリソースをクリーンアップする。"""
        console.print("\n[yellow]🧹 Cleaning up...[/yellow]")
        
        # ブラウザをクリーンアップ
        await self.browser_tools.cleanup()
        
        # 並列セッションをクリーンアップ
        for session in self.parallel_browser_sessions:
            try:
                await session.cleanup()
            except:
                pass
        
        # コードインタープリタをクリーンアップ
        self.analysis_tools.cleanup()
        
        console.print("[green]✅ Cleanup complete[/green]")