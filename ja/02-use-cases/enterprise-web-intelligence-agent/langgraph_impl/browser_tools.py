"""BedrockAgentCore SDK を使用したブラウザ自動化ツール（Playwright および CDP 拡張機能付き）。"""

import asyncio
import uuid
import json
from typing import Dict, List, Optional, Any
from datetime import datetime

import boto3
from playwright.async_api import async_playwright, Browser, Page, BrowserContext, CDPSession
from langchain_core.messages import HumanMessage
from rich.console import Console

# Import from BedrockAgentCore SDK
from bedrock_agentcore.tools.browser_client import BrowserClient
from bedrock_agentcore._utils.endpoints import get_control_plane_endpoint

console = Console()


class BrowserTools:
    """CDP 機能を備えた拡張ブラウザ自動化ツール。"""
    
    def __init__(self, config):
        self.config = config
        self.browser_client = None
        self.browser_id = None
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.cdp_session = None
        self.recording_path = None
        self.llm = None
        self._screenshots_taken = []
        self._discovered_apis = []
        self._performance_metrics = {}
    

    def create_browser_with_recording(self) -> str:
        """Control Plane API を使用して録画設定付きのブラウザを作成する。"""
        console.print("[cyan]🔧 録画設定付きでブラウザを作成中...[/cyan]")
        
        # Create control plane client
        control_plane_url = get_control_plane_endpoint(self.config.region)
        control_client = boto3.client(
            "bedrock-agentcore-control",
            region_name=self.config.region,
            endpoint_url=control_plane_url
        )
        
        # Create browser with recording
        browser_name = f"competitive_intel_{uuid.uuid4().hex[:8]}"
        
        console.print(f"  ブラウザ名: {browser_name}")
        console.print(f"  S3 ロケーション: s3://{self.config.s3_bucket}/{self.config.s3_prefix}")
        console.print(f"  ロール ARN: {self.config.recording_role_arn}")
        
        response = control_client.create_browser(
            name=browser_name,
            executionRoleArn=self.config.recording_role_arn,
            networkConfiguration={
                "networkMode": "PUBLIC"
            },
            recording={
                "enabled": True,
                "s3Location": {
                    "bucket": self.config.s3_bucket,
                    "prefix": self.config.s3_prefix
                }
            }
        )
        
        self.browser_id = response["browserId"]
        
        # NEW: Store the structured recording configuration
        self.recording_config = response.get("recording", {})
        
        # Build recording path for display (but keep structured config)
        s3_location = self.recording_config.get("s3Location", {})
        self.recording_path = f"s3://{s3_location.get('bucket')}/{s3_location.get('prefix')}"
        
        console.print(f"✅ ブラウザを作成しました: {self.browser_id}")
        console.print(f"📹 録画先: {self.recording_path}")
        
        return self.browser_id
    
    async def initialize_browser_session(self, llm):
        """拡張 CDP 機能を備えたブラウザセッションを初期化する。"""
        self.llm = llm
        
        # Create BrowserClient from SDK
        self.browser_client = BrowserClient(region=self.config.region)
        self.browser_client.identifier = self.browser_id
        
        # Start a session
        session_id = self.browser_client.start(
            identifier=self.browser_id,
            name=f"competitive_intel_session_{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            session_timeout_seconds=self.config.browser_session_timeout
        )
        
        console.print(f"✅ セッションを開始しました: {session_id}")
        
        # Get WebSocket headers
        ws_url, headers = self.browser_client.generate_ws_headers()
        console.print(f"[dim]WebSocket URL: {ws_url}[/dim]")
        
        # Wait for browser initialization
        console.print("[yellow]⏳ ブラウザの初期化を待機中...[/yellow]")
        await asyncio.sleep(10)
        
        # Initialize Playwright with CDP
        console.print("[cyan]🎭 CDP サポート付きで Playwright を接続中...[/cyan]")
        self.playwright = await async_playwright().start()
        
        # Connect to the browser via CDP
        self.browser = await self.playwright.chromium.connect_over_cdp(
            ws_url,
            headers=headers
        )
        
        # Get context and page
        self.context = self.browser.contexts[0]
        self.page = self.context.pages[0]
        
        # Create CDP session for advanced features
        try:
            self.cdp_session = await self.context.new_cdp_session(self.page)
            await self._setup_cdp_domains()
            console.print("✅ CDP セッションを初期化しました")
        except Exception as e:
            console.print(f"[yellow]⚠️ CDP セットアップが部分的: {e}[/yellow]")
            self.cdp_session = None
        
        # Set up network interception
        await self._setup_network_interception()
        
        console.print("✅ Playwright が拡張機能付きで接続されました")
        
        # Set recording path
        self.recording_path = f"s3://{self.config.s3_bucket}/{self.config.s3_prefix}{session_id}/"
        console.print(f"📹 録画先: {self.recording_path}")
        
        return self.page
    
    async def _setup_cdp_domains(self):
        """高度な機能のために CDP ドメインを有効化する。"""
        if not self.cdp_session:
            return
            
        try:
            # Enable required CDP domains
            await self.cdp_session.send("Network.enable")
            await self.cdp_session.send("Performance.enable")
            console.print("[dim]✅ CDP ドメインを有効化しました[/dim]")
        except Exception as e:
            console.print(f"[yellow]⚠️ 一部の CDP ドメインが失敗しました: {e}[/yellow]")
    
    async def _setup_network_interception(self):
        """API 検出のためのネットワークリクエストインターセプションを設定する。"""
        def handle_response(response):
            """API を検出するためにネットワークレスポンスを処理する。"""
            try:
                url = response.url
                
                # Skip ad networks and analytics
                skip_domains = [
                    'doubleclick.net', 'googletagmanager.com', 
                    'google-analytics.com', 'facebook.com', 
                    'twitter.com', 'linkedin.com', 'pinterest.com',
                    'amazon-adsystem.com', 'googleadservices.com'
                ]
                if any(domain in url.lower() for domain in skip_domains):
                    return
                
                # Track relevant APIs
                if any(keyword in url.lower() for keyword in ['api', 'price', 'pricing', 'tier', 'plan']):
                    self._discovered_apis.append({
                        'url': url[:100],  # Truncate long URLs
                        'status': response.status,
                        'timestamp': datetime.now().isoformat()
                    })
                    if len(self._discovered_apis) <= 5:  # Limit console output
                        console.print(f"[dim]🔍 API を発見: {url[:60]}...[/dim]")
            except:
                pass
        
        # Set up response handler
        self.page.on("response", handle_response)
    
    async def navigate_to_url(self, url: str) -> Dict:
        """視覚的フィードバックを強化して URL に移動する。"""
        try:
            console.print(f"[cyan]🌐 移動中: {url}[/cyan]")
            
            # Navigate with proper timeout
            await self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
            
            # Wait for dynamic content
            await self.page.wait_for_timeout(3000)
            
            # Get page metrics if CDP is available
            if self.cdp_session:
                try:
                    metrics = await self.cdp_session.send("Performance.getMetrics")
                    self._performance_metrics = {m['name']: m['value'] for m in metrics.get('metrics', [])}
                except:
                    pass
            
            title = await self.page.title()
            
            return {
                "status": "success",
                "url": url,
                "title": title,
                "metrics": self._performance_metrics,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            console.print(f"[red]❌ ナビゲーションエラー: {e}[/red]")
            return {"status": "error", "url": url, "error": str(e)}
    
    async def analyze_forms_and_inputs(self) -> Dict:
        """新機能: ページ上のフォームと入力フィールドを分析する。"""
        console.print("[cyan]📝 フォームと入力フィールドを分析中...[/cyan]")
        
        try:
            # Find all forms on the page
            forms_data = await self.page.evaluate("""
                () => {
                    const forms = Array.from(document.querySelectorAll('form'));
                    return {
                        forms: forms.map(form => ({
                            action: form.action,
                            method: form.method,
                            id: form.id,
                            className: form.className,
                            inputs: Array.from(form.querySelectorAll('input, select, textarea')).map(input => ({
                                type: input.type || input.tagName.toLowerCase(),
                                name: input.name,
                                id: input.id,
                                placeholder: input.placeholder,
                                required: input.required,
                                value: input.type === 'password' ? '[hidden]' : input.value
                            }))
                        })),
                        total_inputs: document.querySelectorAll('input, select, textarea').length,
                        has_file_upload: document.querySelectorAll('input[type="file"]').length > 0,
                        has_password_field: document.querySelectorAll('input[type="password"]').length > 0
                    };
                }
            """)
            
            console.print(f"[green]{len(forms_data['forms'])} 個のフォームと {forms_data['total_inputs']} 個の入力を発見[/green]")
            
            if forms_data['has_file_upload']:
                console.print("[yellow]📎 ページにファイルアップロード機能があります[/yellow]")

            if forms_data['has_password_field']:
                console.print("[yellow]🔐 ページに認証フォームがあります[/yellow]")
            
            return {
                "status": "success",
                **forms_data
            }
            
        except Exception as e:
            console.print(f"[yellow]⚠️ フォーム分析エラー: {e}[/yellow]")
            return {"status": "error", "error": str(e)}

    async def handle_authentication(self, username: str, password: str, form_selector: Optional[str] = None) -> Dict:
        """新機能: ログインページでの認証を処理する。"""
        console.print("[cyan]🔐 認証を処理中...[/cyan]")
        
        try:
            # Find login form
            if not form_selector:
                # Common selectors for login forms
                possible_selectors = [
                    'form[action*="login"]',
                    'form[action*="signin"]',
                    'form#loginForm',
                    'form.login-form',
                    'form'
                ]
                
                for selector in possible_selectors:
                    form = await self.page.query_selector(selector)
                    if form:
                        form_selector = selector
                        break
            
            if not form_selector:
                return {"status": "error", "error": "No login form found"}
            
            # Fill in credentials
            await self.page.fill('input[type="email"], input[type="text"], input[name*="user"]', username)
            await self.page.fill('input[type="password"]', password)
            
            # Submit form
            await self.page.click('button[type="submit"], input[type="submit"]')
            
            # Wait for navigation or response
            await self.page.wait_for_timeout(3000)
            
            # Check if login was successful (simple heuristic)
            current_url = self.page.url
            
            return {
                "status": "success",
                "logged_in": "login" not in current_url.lower(),
                "current_url": current_url
            }
            
        except Exception as e:
            console.print(f"[red]❌ 認証エラー: {e}[/red]")
            return {"status": "error", "error": str(e)}
    
    async def upload_file_to_form(self, file_path: str, selector: str = 'input[type="file"]') -> Dict:
        """新機能: フォームにファイルをアップロードする。"""
        console.print(f"[cyan]📤 ファイルをアップロード中: {file_path}[/cyan]")
        
        try:
            # Find file input
            file_input = await self.page.query_selector(selector)
            if not file_input:
                return {"status": "error", "error": "No file input found"}
            
            # Set the file
            await file_input.set_input_files(file_path)
            
            # Wait for any upload progress
            await self.page.wait_for_timeout(2000)
            
            return {
                "status": "success",
                "file_uploaded": file_path
            }
            
        except Exception as e:
            console.print(f"[red]❌ ファイルアップロードエラー: {e}[/red]")
            return {"status": "error", "error": str(e)}
    
    async def explore_multi_page_workflow(self, target_pages: List[str]) -> List[Dict]:
        """新機能: ワークフロー内の複数ページを探索する。"""
        console.print(f"[cyan]🔄 {len(target_pages)} 件の追加ページを探索中...[/cyan]")
        
        explored_pages = []
        base_url = self.page.url
        
        for target in target_pages:
            try:
                # Try to find and navigate to the page
                console.print(f"[dim]検索中: {target}[/dim]")
                
                # Look for links containing the target keyword
                link_found = False
                selectors = [
                    f'a[href*="{target}"]',
                    f'a:has-text("{target}")',
                    f'nav a:has-text("{target}")',
                    f'[class*="menu"] a:has-text("{target}")'
                ]
                
                for selector in selectors:
                    try:
                        link = await self.page.query_selector(selector)
                        if link:
                            await link.click()
                            await self.page.wait_for_load_state("domcontentloaded")
                            await self.page.wait_for_timeout(2000)
                            
                            # Capture information about this page
                            page_info = {
                                "target": target,
                                "url": self.page.url,
                                "title": await self.page.title(),
                                "found": True,
                                "timestamp": datetime.now().isoformat()
                            }
                            
                            # Take a screenshot
                            await self.take_annotated_screenshot(f"Explored - {target}")
                            
                            explored_pages.append(page_info)
                            console.print(f"[green]✅ 発見して探索しました: {target}[/green]")
                            link_found = True
                            
                            # Go back to base URL for next exploration
                            await self.page.goto(base_url, wait_until="domcontentloaded")
                            break
                    except:
                        continue
                
                if not link_found:
                    explored_pages.append({
                        "target": target,
                        "found": False,
                        "timestamp": datetime.now().isoformat()
                    })
                    console.print(f"[yellow]⚠️ 見つかりませんでした: {target}[/yellow]")
                    
            except Exception as e:
                console.print(f"[yellow]⚠️ {target} の探索エラー: {e}[/yellow]")
                explored_pages.append({
                    "target": target,
                    "found": False,
                    "error": str(e)
                })
        
        return explored_pages
    
    async def execute_javascript_analysis(self, custom_script: Optional[str] = None) -> Dict:
        """新機能: 高度な分析のためにカスタム JavaScript を実行する。"""
        console.print("[cyan]⚡ JavaScript 分析を実行中...[/cyan]")
        
        try:
            if custom_script:
                result = await self.page.evaluate(custom_script)
            else:
                # Default analysis script
                result = await self.page.evaluate("""
                    () => {
                        // Analyze page structure
                        const analysis = {
                            // Count different element types
                            tables: document.querySelectorAll('table').length,
                            forms: document.querySelectorAll('form').length,
                            images: document.querySelectorAll('img').length,
                            videos: document.querySelectorAll('video').length,
                            iframes: document.querySelectorAll('iframe').length,
                            
                            // Check for specific technologies
                            hasReact: window.React !== undefined,
                            hasJQuery: window.jQuery !== undefined,
                            hasAngular: window.angular !== undefined,
                            
                            // Page metrics
                            documentHeight: document.documentElement.scrollHeight,
                            viewportHeight: window.innerHeight,
                            
                            // Interactive elements
                            buttons: document.querySelectorAll('button').length,
                            links: document.querySelectorAll('a').length,
                            
                            // Meta information
                            metaDescription: document.querySelector('meta[name="description"]')?.content,
                            metaKeywords: document.querySelector('meta[name="keywords"]')?.content
                        };
                        
                        return analysis;
                    }
                """)
            
            console.print(f"[green]JavaScript 分析が完了しました[/green]")
            return {
                "status": "success",
                "analysis": result
            }
            
        except Exception as e:
            console.print(f"[red]❌ JavaScript 実行エラー: {e}[/red]")
            return {"status": "error", "error": str(e)}
    
    async def intelligent_scroll_and_discover(self) -> List[Dict]:
        """コンテンツセクションを検出するためにインテリジェントスクロールを実行する。"""
        console.print("[cyan]🔍 ページコンテンツを検出中...[/cyan]")
        discovered_sections = []
        
        try:
            # Get page height
            page_height = await self.page.evaluate("document.body.scrollHeight")
            viewport_height = await self.page.evaluate("window.innerHeight")
            
            # Calculate scroll positions (0%, 25%, 50%, 75%, 100%)
            scroll_positions = [0, 0.25, 0.5, 0.75, 1.0]
            
            for position in scroll_positions:
                current_position = int(page_height * position)
                
                # Smooth scroll
                await self.page.evaluate(f"window.scrollTo({{top: {current_position}, behavior: 'smooth'}})")
                await asyncio.sleep(1)  # Pause to load content
                
                # Look for important sections at this position
                important_selectors = [
                    ('[class*="pric"]', 'Pricing'),
                    ('[class*="tier"]', 'Tiers'),
                    ('[class*="plan"]', 'Plans'),
                    ('[class*="feature"]', 'Features'),
                    ('table', 'Table'),
                    ('form', 'Form'),
                    ('[class*="testimonial"]', 'Testimonials'),
                    ('[class*="faq"]', 'FAQ')
                ]
                
                for selector, label in important_selectors:
                    try:
                        elements = await self.page.query_selector_all(selector)
                        if elements:
                            discovered_sections.append({
                                'selector': selector,
                                'label': label,
                                'count': len(elements),
                                'position': position
                            })
                            console.print(f"[dim]発見: {label} ({len(elements)} 要素)[/dim]")
                    except:
                        pass
            
            # Scroll back to top
            await self.page.evaluate("window.scrollTo({top: 0, behavior: 'smooth'})")
            await asyncio.sleep(1)
            
        except Exception as e:
            console.print(f"[yellow]⚠️ 検出エラー: {e}[/yellow]")
        
        return discovered_sections
    
    async def smart_navigation(self, target: str) -> bool:
        """特定のページセクション（pricing、features など）への移動を試みる。"""
        console.print(f"[cyan]🎯 {target} ページを検索中...[/cyan]")
        
        nav_patterns = {
            "pricing": ["pricing", "price", "plans", "cost", "subscription"],
            "features": ["features", "capabilities", "benefits", "solutions"],
            "docs": ["docs", "documentation", "api", "developers"],
            "about": ["about", "company", "team", "story"]
        }
        
        keywords = nav_patterns.get(target.lower(), [target.lower()])
        
        for keyword in keywords:
            try:
                # Try to find and click a link
                selectors = [
                    f'a[href*="{keyword}"]',
                    f'a:has-text("{keyword}")',
                    f'nav a:has-text("{keyword}")',
                ]
                
                for selector in selectors:
                    try:
                        element = await self.page.query_selector(selector)
                        if element:
                            await element.click()
                            await self.page.wait_for_load_state("domcontentloaded")
                            console.print(f"[green]✅ {target} リンクを発見してクリックしました[/green]")
                            return True
                    except:
                        continue
            except:
                continue
        
        console.print(f"[yellow]⚠️ {target} リンクが見つかりませんでした[/yellow]")
        return False
    
    async def extract_pricing_info(self) -> Dict:
        """視覚的フィードバック付きで価格情報を抽出する。"""
        try:
            console.print("[cyan]💰 価格情報を抽出中...[/cyan]")
            
            # First do intelligent scroll to find pricing sections
            discovered = await self.intelligent_scroll_and_discover()
            
            # Find pricing elements
            pricing_selectors = [
                '[class*="price"], [class*="Price"]',
                '[class*="pricing"], [class*="Pricing"]',
                '[class*="tier"], [class*="Tier"]',
                '[class*="plan"], [class*="Plan"]',
            ]
            
            found_elements = []
            for selector in pricing_selectors:
                try:
                    elements = await self.page.query_selector_all(selector)
                    for element in elements[:5]:
                        text = await element.text_content()
                        if text and len(text.strip()) > 0:
                            found_elements.append(text.strip())
                except:
                    pass
            
            # Get text content - LIMIT TO PREVENT TOKEN OVERFLOW
            text_content = await self.page.evaluate("() => document.body.innerText")
            
            # Truncate to avoid token limits
            max_chars = 10000
            if len(text_content) > max_chars:
                text_content = text_content[:max_chars]
                console.print(f"[yellow]⚠️ コンテンツを {max_chars} 文字に切り詰めました[/yellow]")
            
            # LLM extraction
            extraction_prompt = f"""
            Analyze this webpage and extract pricing information.
            
            URL: {self.page.url}
            Found elements: {json.dumps(found_elements[:20])}
            
            Text (truncated):
            {text_content}
            
            Extract: prices, tiers, features per tier, billing cycles.
            Return as concise JSON.
            """
            
            response = await self.llm.ainvoke([HumanMessage(content=extraction_prompt)])
            
            return {
                "status": "success",
                "data": response.content,
                "visual_elements": found_elements[:20],
                "discovered_sections": discovered,
                "url": self.page.url,
                "extracted_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            error_msg = str(e)
            if "ThrottlingException" in error_msg or "ValidationException" in error_msg:
                console.print(f"[yellow]⚠️ LLM 制限に達しました、部分データを返します[/yellow]")
                return {
                    "status": "partial",
                    "visual_elements": found_elements[:20] if 'found_elements' in locals() else [],
                    "url": self.page.url
                }
            console.print(f"[red]❌ 抽出エラー: {e}[/red]")
            return {"status": "error", "error": str(e)}
    
    async def extract_product_features(self) -> Dict:
        """ページから製品機能を抽出する。"""
        try:
            console.print("[cyan]🔍 製品機能を抽出中...[/cyan]")
            
            # Get text content - LIMITED
            text_content = await self.page.evaluate("() => document.body.innerText")
            
            max_chars = 8000
            if len(text_content) > max_chars:
                text_content = text_content[:max_chars]
            
            extraction_prompt = f"""
            Extract key product features from this page.
            URL: {self.page.url}
            
            Content:
            {text_content}
            
            List top 10 features as JSON. Be concise.
            """
            
            response = await self.llm.ainvoke([HumanMessage(content=extraction_prompt)])
            
            return {
                "status": "success",
                "data": response.content,
                "url": self.page.url,
                "extracted_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            if "ThrottlingException" in str(e) or "ValidationException" in str(e):
                return {"status": "partial", "error": "Rate limited", "url": self.page.url}
            return {"status": "error", "error": str(e)}
    
    async def take_annotated_screenshot(self, description: str = "") -> Dict:
        """注釈オーバーレイ付きのスクリーンショットを撮影する。"""
        try:
            console.print(f"[cyan]📸 スクリーンショットを撮影: {description}[/cyan]")
            
            # Add annotation to the page (safe way without innerHTML)
            if description:
                await self.page.evaluate(f"""
                    () => {{
                        const annotation = document.createElement('div');
                        annotation.id = 'screenshot-annotation';
                        annotation.style.cssText = 'position: fixed; top: 10px; left: 10px; background: rgba(0,0,0,0.8); color: white; padding: 10px; border-radius: 8px; z-index: 99999; font-family: monospace;';
                        annotation.textContent = '{description} - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}';
                        document.body.appendChild(annotation);
                    }}
                """)
            
            # Take screenshot
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_path = f"screenshot_{timestamp}.png"
            
            await self.page.screenshot(path=screenshot_path, full_page=False)
            
            # Remove annotation
            if description:
                await self.page.evaluate("""
                    () => {
                        const annotation = document.getElementById('screenshot-annotation');
                        if (annotation) annotation.remove();
                    }
                """)
            
            screenshot_info = {
                "description": description,
                "timestamp": datetime.now().isoformat(),
                "url": self.page.url,
                "path": screenshot_path
            }
            self._screenshots_taken.append(screenshot_info)
            
            # Clean up local file
            import os
            if os.path.exists(screenshot_path):
                os.remove(screenshot_path)
            
            return {
                "status": "success",
                "screenshot": screenshot_info,
                "total_screenshots": len(self._screenshots_taken)
            }
            
        except Exception as e:
            console.print(f"[yellow]⚠️ スクリーンショットエラー: {e}[/yellow]")
            return {"status": "error", "error": str(e)}
    
    async def capture_performance_metrics(self) -> Dict:
        """CDP を使用してパフォーマンスメトリクスをキャプチャする。"""
        if not self.cdp_session:
            return {}
        
        try:
            metrics = await self.cdp_session.send("Performance.getMetrics")
            return {m['name']: m['value'] for m in metrics.get('metrics', [])}
        except:
            return {}
    
    def take_control(self):
        """ブラウザの手動制御を取得する。"""
        if self.browser_client:
            console.print("[yellow]🎮 手動制御を取得中...[/yellow]")
            self.browser_client.take_control()
            console.print("✅ 手動制御が有効になりました")
    
    def release_control(self):
        """手動制御を解除する。"""
        if self.browser_client:
            console.print("[yellow]🤖 制御を解放中...[/yellow]")
            self.browser_client.release_control()
            console.print("✅ 自動化が復元されました")
    
    async def cleanup(self):
        """ブラウザリソースをクリーンアップする。"""
        if self.cdp_session:
            try:
                await self.cdp_session.detach()
            except:
                pass

        if self.browser:
            console.print("[yellow]🎭 ブラウザを閉じています...[/yellow]")
            await self.browser.close()

        if self.playwright:
            console.print("[yellow]🎭 Playwright を停止しています...[/yellow]")
            await self.playwright.stop()

        if self.browser_client:
            console.print("[yellow]🛑 セッションを停止しています...[/yellow]")
            self.browser_client.stop()
            console.print("✅ クリーンアップが完了しました")