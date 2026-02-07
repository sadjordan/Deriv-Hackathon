"""
Playwright Browser Manager for Mobile Emulation
Handles browser initialization with iPhone 13 configuration
"""

from typing import Optional
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page, Playwright
import logging

logger = logging.getLogger(__name__)


class BrowserManager:
    """Manages Playwright browser instance with mobile emulation"""
    
    def __init__(self, headless: bool = False):
        """
        Initialize browser manager
        
        Args:
            headless: Whether to run browser in headless mode (default: False for debugging)
        """
        self.headless = headless
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
        Start browser with iPhone 13 mobile emulation
        
        Returns:
            Page: Playwright page object
        """
        logger.info("Starting Playwright browser with iPhone 13 emulation")
        
        # Initialize Playwright
        self.playwright = sync_playwright().start()
        
        # Launch Chromium browser
        self.browser = self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--disable-blink-features=AutomationControlled',  # Avoid detection
            ]
        )
        
        # Get iPhone 13 device configuration
        device = self.playwright.devices['iPhone 13']
        
        # Create context with mobile emulation
        self.context = self.browser.new_context(
            **device,
            locale='en-US',
            timezone_id='America/New_York',
            permissions=['geolocation'],  # Grant location if needed
            accept_downloads=False,
        )
        
        # Enable network interception for monitoring
        # This will be used in Phase 3 for API error detection
        self.context.route('**/*', lambda route: route.continue_())
        
        # Create new page
        self.page = self.context.new_page()
        
        # Set default timeout
        self.page.set_default_timeout(30000)  # 30 seconds
        
        logger.info(f"Browser started - Viewport: {device['viewport']}")
        
        return self.page
    
    def navigate(self, url: str) -> None:
        """
        Navigate to a URL
        
        Args:
            url: Target URL to navigate to
        """
        if not self.page:
            raise RuntimeError("Browser not started. Call start() first.")
        
        logger.info(f"Navigating to: {url}")
        self.page.goto(url, wait_until='networkidle')
        
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
            self.page.close()
            self.page = None
            
        if self.context:
            self.context.close()
            self.context = None
            
        if self.browser:
            self.browser.close()
            self.browser = None
            
        if self.playwright:
            self.playwright.stop()
            self.playwright = None


# Convenience function for quick usage
def create_mobile_browser(headless: bool = False) -> BrowserManager:
    """
    Create and return a BrowserManager instance
    
    Args:
        headless: Whether to run in headless mode
        
    Returns:
        BrowserManager: Configured browser manager
    """
    return BrowserManager(headless=headless)
