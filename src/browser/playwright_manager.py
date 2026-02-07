"""
Playwright Browser Manager with Browserless.io Support
Handles browser initialization with local or cloud-based stealth browser
"""

import os
from typing import Optional
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page, Playwright
import logging

logger = logging.getLogger(__name__)


class BrowserManager:
    """Manages Playwright browser instance with optional Browserless.io cloud support"""
    
    def __init__(
        self, 
        headless: bool = False,
        use_browserless: bool = False,
        browserless_api_key: Optional[str] = None,
        solve_captchas: bool = True
    ):
        """
        Initialize browser manager
        
        Args:
            headless: Whether to run browser in headless mode (default: False for debugging)
            use_browserless: Whether to use browserless.io cloud browser for stealth
            browserless_api_key: API key for browserless.io (or use BROWSERLESS_API_KEY env var)
            solve_captchas: Whether to enable automatic CAPTCHA solving (browserless.io only)
        """
        self.headless = headless
        self.use_browserless = use_browserless
        self.browserless_api_key = browserless_api_key or os.getenv('BROWSERLESS_API_KEY')
        self.solve_captchas = solve_captchas
        
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        
    def __enter__(self):
        """Context manager entry - start browser"""
        self.start()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup browser"""
        self.close()
        
    def start(self) -> Page:
        """
        Start browser - either local or via Browserless.io cloud
        
        Returns:
            Page: Playwright page object
        """
        # Initialize Playwright
        self.playwright = sync_playwright().start()
        
        if self.use_browserless:
            return self._start_browserless()
        else:
            return self._start_local()
    
    def _start_browserless(self) -> Page:
        """
        Start browser via Browserless - either local Docker or cloud service
        
        Returns:
            Page: Playwright page object
        """
        # Determine WebSocket URL - local Docker or cloud
        browserless_url = os.getenv('BROWSERLESS_URL', 'ws://localhost:3000')
        
        if browserless_url.startswith('ws://localhost') or browserless_url.startswith('ws://127.0.0.1'):
            # Local Docker instance - no API key needed
            ws_url = browserless_url
            logger.info(f"Connecting to local Browserless Docker at {ws_url}")
        else:
            # Cloud service - requires API key
            if not self.browserless_api_key:
                raise ValueError(
                    "Browserless API key required for cloud. Set BROWSERLESS_API_KEY env var or use local Docker."
                )
            
            # Build browserless.io cloud WebSocket URL
            ws_params = [f"token={self.browserless_api_key}"]
            
            if self.solve_captchas:
                ws_params.append("solveCaptchas=true")
            
            ws_params.append("stealth=true")
            ws_params.append("blockAds=true")
            
            ws_url = f"wss://chrome.browserless.io?{'&'.join(ws_params)}"
            logger.info("Connecting to Browserless.io cloud with stealth mode")
        
        # Connect to browserless via CDP
        self.browser = self.playwright.chromium.connect_over_cdp(ws_url)
        
        # Get the default context from browserless
        contexts = self.browser.contexts
        if contexts:
            self.context = contexts[0]
        else:
            # Create new context if none exists
            self.context = self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                locale='en-US',
                timezone_id='America/New_York',
            )
        
        # Get the default page or create new one
        pages = self.context.pages
        if pages:
            self.page = pages[0]
        else:
            self.page = self.context.new_page()
        
        # Set viewport for desktop
        self.page.set_viewport_size({'width': 1920, 'height': 1080})
        
        # Set default timeout
        self.page.set_default_timeout(60000)  # 60 seconds for cloud (network latency)
        
        logger.info("Connected to Browserless.io - Stealth mode active, CAPTCHA solving enabled")
        
        return self.page
    
    def _start_local(self) -> Page:
        """
        Start local browser with iPhone 13 mobile viewport and touchscreen
        
        Returns:
            Page: Playwright page object
        """
        logger.info("Starting local Playwright browser with iPhone 13 mobile viewport")
        
        # Launch Chromium browser locally
        self.browser = self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--disable-blink-features=AutomationControlled',  # Avoid detection
                '--disable-features=IsolateOrigins,site-per-process',
                '--no-sandbox',
            ]
        )
        
        # iPhone 13 viewport configuration (390x844)
        viewport = {'width': 390, 'height': 844}
        
        # Create context with iPhone 13 mobile configuration and touchscreen
        self.context = self.browser.new_context(
            viewport=viewport,
            user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1',
            locale='en-US',
            timezone_id='America/New_York',
            permissions=['geolocation'],
            accept_downloads=False,
            has_touch=True,  # Enable touchscreen for mobile gestures
            is_mobile=True,  # Enable mobile mode
            device_scale_factor=3,  # iPhone 13 has 3x pixel density
        )
        
        # Enable network interception for monitoring
        self.context.route('**/*', lambda route: route.continue_())
        
        # Create new page
        self.page = self.context.new_page()
        
        # Set default timeout
        self.page.set_default_timeout(30000)  # 30 seconds
        
        logger.info(f"Local browser started - Viewport: {viewport}")
        
        return self.page
    
    def navigate(self, url: str) -> None:
        """
        Navigate to a URL
        
        Args:
            url: Target URL to navigate to
        """
        if not self.page:
            raise RuntimeError("Browser not started. Call start() first.")
        
        if not self.is_page_alive():
            logger.warning("Page is closed, attempting to restart browser...")
            self.close()
            self.start()
        
        logger.info(f"Navigating to: {url}")
        self.page.goto(url, wait_until='networkidle')
    
    def is_page_alive(self) -> bool:
        """
        Check if the browser page is still alive and connected
        
        Returns:
            bool: True if page is alive, False if closed or disconnected
        """
        if not self.page:
            return False
        
        try:
            # Try a simple operation to check if page is still alive
            self.page.evaluate("1")
            return True
        except Exception:
            logger.warning("Page connection lost")
            return False
        
    def get_page(self) -> Page:
        """
        Get current page instance
        
        Returns:
            Page: Current Playwright page
        """
        if not self.page:
            raise RuntimeError("Browser not started. Call start() first.")
        return self.page
    
    def get_viewport_size(self) -> dict:
        """
        Get current viewport dimensions
        
        Returns:
            dict: {'width': int, 'height': int}
        """
        if not self.page:
            raise RuntimeError("Browser not started. Call start() first.")
        return self.page.viewport_size
    
    def close(self) -> None:
        """Cleanup browser resources"""
        logger.info("Closing browser")
        
        if self.page:
            try:
                self.page.close()
            except Exception:
                pass  # Page may already be closed
            self.page = None
            
        if self.context:
            try:
                self.context.close()
            except Exception:
                pass
            self.context = None
            
        if self.browser:
            try:
                self.browser.close()
            except Exception:
                pass
            self.browser = None
            
        if self.playwright:
            try:
                self.playwright.stop()
            except Exception:
                pass
            self.playwright = None


# Convenience functions
def create_local_browser(headless: bool = False) -> BrowserManager:
    """
    Create a local BrowserManager instance
    
    Args:
        headless: Whether to run in headless mode
        
    Returns:
        BrowserManager: Configured for local browser
    """
    return BrowserManager(headless=headless, use_browserless=False)


def create_browserless_browser(
    api_key: Optional[str] = None, 
    solve_captchas: bool = True
) -> BrowserManager:
    """
    Create a Browserless.io cloud BrowserManager instance
    
    Args:
        api_key: Browserless.io API key (or use BROWSERLESS_API_KEY env var)
        solve_captchas: Whether to enable automatic CAPTCHA solving
        
    Returns:
        BrowserManager: Configured for Browserless.io cloud
    """
    return BrowserManager(
        headless=True,  # Browserless is always headless
        use_browserless=True,
        browserless_api_key=api_key,
        solve_captchas=solve_captchas
    )
