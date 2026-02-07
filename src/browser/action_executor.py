"""
Action Executor
Executes actions (click, type, scroll) on the page using coordinates
"""

import logging
import time
from typing import Tuple
from playwright.sync_api import Page

logger = logging.getLogger(__name__)


class ActionExecutor:
    """Executes browser actions based on coordinates"""
    
    def __init__(self, page: Page):
        """
        Initialize action executor
        
        Args:
            page: Playwright page object
        """
        self.page = page
    
    def click(self, x: int, y: int, label: str = "") -> bool:
        """
        Click at specific coordinates
        
        Args:
            x: X coordinate in pixels
            y: Y coordinate in pixels
            label: Optional label for logging
            
        Returns:
            True if action succeeded
        """
        try:
            log_msg = f"Clicking at ({x}, {y})"
            if label:
                log_msg += f" - {label}"
            logger.info(log_msg)
            
            # Validate coordinates are within viewport
            viewport = self.page.viewport_size
            if not (0 <= x <= viewport['width'] and 0 <= y <= viewport['height']):
                logger.error(f"Coordinates ({x}, {y}) outside viewport {viewport}")
                return False
            
            # Perform click using mouse
            self.page.mouse.click(x, y)
            
            # Small delay to allow for UI response
            time.sleep(0.5)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to click at ({x}, {y}): {e}")
            return False
    
    def type_text(self, x: int, y: int, text: str, press_enter: bool = False) -> bool:
        """
        Click at coordinates and type text
        
        Args:
            x: X coordinate
            y: Y coordinate
            text: Text to type
            press_enter: Whether to press Enter after typing
            
        Returns:
            True if action succeeded
        """
        try:
            logger.info(f"Typing text at ({x}, {y}): '{text}'" + (" [+Enter]" if press_enter else ""))
            
            # Click to focus
            if not self.click(x, y, "input field"):
                return False
            
            # Wait for focus
            time.sleep(0.3)
            
            self.page.keyboard.press('Meta+a')  # Cmd+A on Mac
            time.sleep(0.1)
            self.page.keyboard.press('Backspace')
            time.sleep(0.1)
            
            # Type text with faster delay to reduce autocomplete interference
            self.page.keyboard.type(text, delay=30)  # 30ms between keystrokes
            
            # Press Enter if requested
            if press_enter:
                time.sleep(0.2)
                self.page.keyboard.press('Enter')
                time.sleep(0.5)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to type text: {e}")
            return False
    
    def press_key(self, key: str) -> bool:
        """
        Press a specific key (Enter, Tab, Escape, etc.)
        
        Args:
            key: Key to press (Enter, Tab, Escape, Backspace, etc.)
            
        Returns:
            True if action succeeded
        """
        try:
            logger.info(f"Pressing key: {key}")
            self.page.keyboard.press(key)
            time.sleep(0.3)
            return True
            
        except Exception as e:
            logger.error(f"Failed to press key '{key}': {e}")
            return False
    
    def type_and_submit(self, x: int, y: int, text: str) -> bool:
        """
        Click at coordinates, type text, and press Enter to submit
        
        Args:
            x: X coordinate
            y: Y coordinate
            text: Text to type
            
        Returns:
            True if action succeeded
        """
        return self.type_text(x, y, text, press_enter=True)
    
    def go_back(self) -> bool:
        """
        Navigate to the previous page in browser history
        
        Returns:
            True if action succeeded
        """
        try:
            logger.info("Going back to previous page")
            self.page.go_back(timeout=5000)
            time.sleep(1.0)  # Wait for page to load
            return True
            
        except Exception as e:
            logger.error(f"Failed to go back: {e}")
            return False
    
    def scroll(self, direction: str = "down", amount: int = 300) -> bool:
        """
        Scroll the page vertically
        
        Args:
            direction: 'up' or 'down'
            amount: Pixels to scroll
            
        Returns:
            True if action succeeded
        """
        try:
            logger.info(f"Scrolling {direction} by {amount}px")
            
            # Get current scroll position
            current_scroll = self.page.evaluate("window.pageYOffset")
            
            # Calculate target scroll
            if direction == "down":
                target_scroll = current_scroll + amount
            else:
                target_scroll = max(0, current_scroll - amount)
            
            # Perform scroll
            self.page.evaluate(f"window.scrollTo(0, {target_scroll})")
            
            # Wait for scroll to complete
            time.sleep(0.5)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to scroll: {e}")
            return False
    
    def wait(self, seconds: float = 1.0) -> bool:
        """
        Explicit wait
        
        Args:
            seconds: Number of seconds to wait
            
        Returns:
            True
        """
        logger.info(f"Waiting for {seconds} seconds")
        time.sleep(seconds)
        return True
    
    def tap(self, x: int, y: int, label: str = "") -> bool:
        """
        Mobile-style tap (alias for click with touch behavior)
        
        Args:
            x: X coordinate
            y: Y coordinate
            label: Optional label
            
        Returns:
            True if succeeded
        """
        try:
            log_msg = f"Tapping at ({x}, {y})"
            if label:
                log_msg += f" - {label}"
            logger.info(log_msg)
            
            # Use touchscreen tap for mobile
            self.page.touchscreen.tap(x, y)
            time.sleep(0.5)
            
            return True
            
        except Exception as e:
            # Fallback to regular click
            logger.warning(f"Tap failed, falling back to click: {e}")
            return self.click(x, y, label)
    
    def swipe(
        self,
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int,
        duration_ms: int = 300
    ) -> bool:
        """
        Perform swipe gesture (for mobile scrolling/swiping)
        
        Args:
            start_x: Starting X coordinate
            start_y: Starting Y coordinate
            end_x: Ending X coordinate
            end_y: Ending Y coordinate
            duration_ms: Duration of swipe in milliseconds
            
        Returns:
            True if succeeded
        """
        try:
            logger.info(f"Swiping from ({start_x}, {start_y}) to ({end_x}, {end_y})")
            
            # Perform swipe using touch
            self.page.mouse.move(start_x, start_y)
            self.page.mouse.down()
            
            # Move to end position
            steps = duration_ms // 16  # ~60fps
            for i in range(steps + 1):
                progress = i / steps
                x = start_x + (end_x - start_x) * progress
                y = start_y + (end_y - start_y) * progress
                self.page.mouse.move(x, y)
                time.sleep(0.016)  # ~16ms per frame
            
            self.page.mouse.up()
            time.sleep(0.3)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to swipe: {e}")
            return False
    
    def validate_viewport_coordinates(self, x: int, y: int) -> bool:
        """
        Check if coordinates are within current viewport
        
        Args:
            x: X coordinate
            y: Y coordinate
            
        Returns:
            True if coordinates are valid
        """
        viewport = self.page.viewport_size
        return 0 <= x <= viewport['width'] and 0 <= y <= viewport['height']
    
    def get_current_url(self) -> str:
        """Get current page URL"""
        return self.page.url
    
    def wait_for_navigation(self, timeout: int = 5000) -> bool:
        """
        Wait for navigation to complete
        
        Args:
            timeout: Timeout in milliseconds
            
        Returns:
            True if navigation detected
        """
        try:
            self.page.wait_for_load_state('networkidle', timeout=timeout)
            return True
        except:
            return False
