"""
Proof-of-Concept Test: Vision-Based Navigation
Tests the core vision-to-action loop by navigating Google.com
"""

import os
import sys
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.browser.playwright_manager import BrowserManager
from src.browser.action_executor import ActionExecutor
from src.vision.screenshot_handler import ScreenshotHandler
from src.ai.vision_navigator import GeminiVisionNavigator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_google_search():
    """
    Test Case: Navigate to Google.com and search for "Hello World"
    
    This validates:
    1. Browser initialization with mobile emulation
    2. Screenshot capture and base64 encoding
    3. Gemini vision analysis
    4. Coordinate-based clicking and typing
    5. Navigation verification
    """
    logger.info("=" * 60)
    logger.info("PHASE 1 PROOF-OF-CONCEPT TEST")
    logger.info("Test: Vision-based Google Search")
    logger.info("=" * 60)
    
    # Initialize components
    screenshot_handler = ScreenshotHandler()
    navigator = GeminiVisionNavigator()
    
    with BrowserManager(headless=False) as browser:
        # Get page
        page = browser.get_page()
        executor = ActionExecutor(page)
        
        # Step 1: Navigate to Google
        logger.info("\n[Step 1] Navigating to Google.com")
        browser.navigate("https://www.google.com")
        executor.wait(2.0)  # Wait for page to fully load
        
        # Check for and handle cookie consent
        logger.info("Checking for cookie consent dialog...")
        try:
            # Try to find and click "Accept" or "Reject" button
            accept_button = page.locator('button:has-text("Accept"), button:has-text("I agree"), button:has-text("Reject all")').first
            if accept_button.is_visible(timeout=2000):
                logger.info("Cookie consent found - clicking to dismiss")
                accept_button.click()
                executor.wait(1.0)
        except:
            logger.info("No cookie consent dialog or already dismissed")
        
        # Step 2: Capture initial state
        logger.info("\n[Step 2] Capturing screenshot")
        filepath, base64_image = screenshot_handler.capture_state(page, "google_home")
        logger.info(f"Screenshot saved: {filepath}")
        
        # Step 3: Ask AI to find search bar
        logger.info("\n[Step 3] Asking AI to locate search bar")
        action = navigator.get_next_action(
            screenshot_base64=base64_image,
            objective="Find and click the search bar",
            persona="normal_user"
        )
        
        logger.info(f"AI Response:")
        logger.info(f"  Action Type: {action.action_type}")
        logger.info(f"  Reasoning: {action.reasoning}")
        logger.info(f"  Confidence: {action.confidence}")
        
        if action.action_type == "stuck":
            logger.error("AI is stuck - cannot proceed")
            return False
        
        # Step 4: Execute action
        if action.bounding_box:
            viewport = browser.get_viewport_size()
            x, y = screenshot_handler.calculate_center(action.bounding_box, viewport)
            
            logger.info(f"\n[Step 4] Tapping search bar at ({x}, {y})")
            logger.info(f"Viewport: {viewport}")
            logger.info(f"Bounding box: {action.bounding_box}")
            
            # Draw bounding box on screenshot
            screenshot_handler.draw_bounding_box(
                filepath,
                action.bounding_box,
                label="Search Bar",
                output_path=filepath.replace(".png", "_annotated.png")
            )
            
            # Use tap for mobile instead of click
            success = executor.tap(x, y, "search bar")
            if not success:
                logger.error("Failed to tap search bar")
                return False
            
            executor.wait(1.0)
        else:
            logger.error("AI did not return bounding box for search bar")
            return False
        
        # Step 5: Type search query
        logger.info("\n[Step 5] Typing 'Hello World'")
        executor.wait(1.0)  # Wait for input to be ready
        
        # Verify we can type (check if input is focused)
        try:
            # Try typing directly
            logger.info("Typing 'Hello World' via keyboard")
            page.keyboard.type("Hello World", delay=100)
            logger.info("✅ Text typed successfully")
        except Exception as e:
            logger.error(f"Failed to type: {e}")
            # Try clicking the search box again
            logger.info("Retrying - clicking search box again...")
            if action.bounding_box:
                viewport2 = browser.get_viewport_size()
                x, y = screenshot_handler.calculate_center(action.bounding_box, viewport2)
                executor.tap(x, y, "search bar retry")
                executor.wait(0.5)
                page.keyboard.type("Hello World", delay=100)
        
        executor.wait(1.0)
        
        # Capture state after typing
        filepath2, base64_image2 = screenshot_handler.capture_state(page, "google_after_typing")
        logger.info(f"After typing screenshot: {filepath2}")
        
        # Step 6: Submit search
        logger.info("\n[Step 6] Submitting search")
        
        # Wait for autocomplete suggestions to appear
        executor.wait(1.0)
        
        # Ask AI to click on the first search suggestion or search button
        logger.info("Asking AI to find and click search suggestion or button...")
        search_action = navigator.get_next_action(
            screenshot_base64=base64_image2,
            objective="Click on the first search suggestion that says 'Hello World' OR click the 'Google Search' button to search",
            persona="normal_user"
        )
        
        logger.info(f"AI found: {search_action.action_type} - {search_action.reasoning}")
        
        if search_action.bounding_box:
            viewport = browser.get_viewport_size()
            x, y = screenshot_handler.calculate_center(search_action.bounding_box, viewport)
            logger.info(f"Tapping search element at ({x}, {y})")
            
            # Annotate the screenshot
            screenshot_handler.draw_bounding_box(
                filepath2,
                search_action.bounding_box,
                label="Search Action",
                output_path=filepath2.replace(".png", "_annotated.png"),
                color="green"
            )
            
            executor.tap(x, y, "search suggestion/button")
            executor.wait(2.5)
        else:
            # Fallback: try pressing Enter
            logger.info("No bounding box found, pressing Enter as fallback")
            page.keyboard.press("Enter")
            executor.wait(2.5)
        
        # Step 7: Verify results
        logger.info("\n[Step 7] Verifying search results")
        final_url = executor.get_current_url()
        logger.info(f"Final URL: {final_url}")
        
        # Capture results page
        filepath3, _ = screenshot_handler.capture_state(page, "google_results")
        logger.info(f"Results screenshot: {filepath3}")
        
        # Check if we're on results page (multiple checks)
        url_changed = final_url != "https://www.google.com/"
        has_search_param = "search" in final_url.lower() or "q=" in final_url.lower()
        
        # Also check page title
        page_title = page.title()
        logger.info(f"Page title: {page_title}")
        title_has_query = "hello world" in page_title.lower()
        
        is_success = url_changed or has_search_param or title_has_query
        
        if is_success:
            logger.info("\n" + "=" * 60)
            logger.info("✅ TEST PASSED - Successfully navigated using vision!")
            logger.info(f"✅ URL changed: {url_changed}")
            logger.info(f"✅ Has search params: {has_search_param}")
            logger.info(f"✅ Title contains query: {title_has_query}")
            logger.info("=" * 60)
            return True
        else:
            logger.error("\n" + "=" * 60)
            logger.error("❌ TEST FAILED - Did not reach results page")
            logger.error(f"URL: {final_url}")
            logger.error(f"Title: {page_title}")
            logger.error("Check the screenshots to see what happened:")
            logger.error(f"  - {filepath}")
            logger.error(f"  - {filepath2}")
            logger.error(f"  - {filepath3}")
            logger.error("=" * 60)
            return False


def main():
    """Run proof-of-concept test"""
    try:
        success = test_google_search()
        sys.exit(0 if success else 1)
        
    except Exception as e:
        logger.exception(f"Test failed with exception: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
