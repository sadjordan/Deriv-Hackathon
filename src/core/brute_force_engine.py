"""
Brute Force Engine - Systematically explores every interactive element
"""

import logging
import os
import signal
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from .element_discovery import ElementDiscovery, InteractiveElement
from .site_mapper import SiteMap
from src.alerting.teams_notifier import TeamsNotifier

logger = logging.getLogger(__name__)


class BruteForceEngine:
    """
    Systematically explores every interactive element on the app.

    Algorithm:
    1. Start at target URL
    2. Discover all interactive elements on current screen
    3. Click each element one at a time
    4. Record result (navigation, error, no change)
    5. Navigate back to original screen
    6. After all elements tested, move to next unvisited screen
    7. Repeat until all screens fully tested
    """

    def __init__(
        self,
        api_key: str,
        target_url: str,
        sitemap_dir: str = "sitemap",
        log_dir: str = "brute_force_logs",
        teams_webhook_url: Optional[str] = None,
    ):
        self.api_key = api_key
        self.target_url = target_url
        self.site_map = SiteMap(save_dir=sitemap_dir)

        # Lazy imports to avoid circular dependencies
        self.browser_manager = None
        self.screenshot_handler = None
        self.vision_navigator = None
        self.element_discovery = None
        self.logger = None

        self._running = False
        self._stop_requested = False
        self._current_run_id = None

        # Stats
        self.stats = {
            "elements_tested": 0,
            "errors_found": 0,
            "screens_discovered": 0,
            "current_screen": None,
            "uptime_seconds": 0,
            "run_number": 0,
        }

        # Teams notifier
        self.teams_notifier = TeamsNotifier(teams_webhook_url)

    def _initialize_components(self):
        """Initialize browser and AI components"""
        from src.browser.playwright_manager import BrowserManager
        from src.vision.screenshot_handler import ScreenshotHandler
        from src.ai.vision_navigator import GeminiVisionNavigator
        from src.diagnostics.brute_force_logger import BruteForceLogger

        self.browser_manager = BrowserManager(headless=True)
        self.browser_manager.start()  # Must call start() before navigate()
        self.screenshot_handler = ScreenshotHandler()
        self.vision_navigator = GeminiVisionNavigator(api_key=self.api_key)
        self.element_discovery = ElementDiscovery(self.vision_navigator)
        self.logger = BruteForceLogger(log_dir="brute_force_logs")

    def _cleanup_components(self):
        """Cleanup browser resources"""
        if self.browser_manager:
            try:
                self.browser_manager.close()
            except:
                pass
        self.browser_manager = None

    def run_exploration(
        self, max_screens: int = 50, timeout_minutes: int = 60, resume: bool = True
    ) -> dict:
        """
        Run a single exploration cycle.

        Args:
            max_screens: Maximum screens to explore
            timeout_minutes: Timeout for the run
            resume: Whether to resume from saved site map

        Returns:
            dict with run stats
        """
        self._running = True
        self._stop_requested = False
        self._current_run_id = str(uuid.uuid4())[:8]

        start_time = time.time()
        timeout_seconds = timeout_minutes * 60

        try:
            # Initialize
            self._initialize_components()

            # Try to load existing site map
            if resume:
                self.site_map.load_from_disk()

            # Start logging
            self.logger.start_run(self._current_run_id)

            # Navigate to target
            self.browser_manager.navigate(self.target_url)
            time.sleep(2)  # Wait for page load

            # Main exploration loop
            screens_explored = 0

            while self._running and not self._stop_requested:
                # Check timeout
                elapsed = time.time() - start_time
                if elapsed > timeout_seconds:
                    logger.info("Timeout reached, ending exploration")
                    break

                # Check screen limit
                if len(self.site_map.screens) >= max_screens:
                    logger.info("Max screens reached")
                    break

                # Capture current screen
                screen_fp = self._capture_current_screen()
                if not screen_fp:
                    break

                # Get untested elements
                untested = self.site_map.get_untested_elements(screen_fp)

                if not untested:
                    # This screen is done, find next
                    next_screen = self.site_map.get_next_screen_to_explore()
                    if not next_screen:
                        logger.info("All screens fully tested!")
                        break

                    # Navigate to next screen (reload target for now)
                    self.browser_manager.navigate(self.target_url)
                    time.sleep(2)
                    screens_explored += 1
                    continue

                # Test next element
                element = untested[0]
                self._test_element(screen_fp, element)

                # Update stats
                self.stats["elements_tested"] += 1
                self.stats["screens_discovered"] = len(self.site_map.screens)
                self.stats["uptime_seconds"] = time.time() - start_time

            # Save site map
            self.site_map.save_to_disk()

        except Exception as e:
            logger.error(f"Exploration failed: {e}")
        finally:
            summary = self.logger.end_run() if self.logger else None
            self._cleanup_components()
            self._running = False

            # Send Teams notification on exploration completion
            self._send_exploration_completion_notification()

        return self.site_map.get_coverage_stats()

    def _send_exploration_completion_notification(self) -> None:
        """Send Teams notification when exploration cycle completes"""
        coverage_stats = self.site_map.get_coverage_stats()

        # Determine severity based on errors found
        if self.stats["errors_found"] > 0:
            severity = "P1" if self.stats["errors_found"] > 5 else "P2"
            status_emoji = "⚠️"
        else:
            severity = "P3"
            status_emoji = "✅"

        # Build description
        description = (
            f"Brute Force exploration cycle #{self.stats['run_number']} completed.\n\n"
        )
        description += f"**Target URL:** {self.target_url}\n"
        description += (
            f"**Screens Discovered:** {coverage_stats.get('screens_count', 0)}\n"
        )
        description += f"**Elements Tested:** {self.stats['elements_tested']}\n"
        description += (
            f"**Total Elements:** {coverage_stats.get('total_elements', 0)}\n"
        )
        description += (
            f"**Coverage:** {coverage_stats.get('coverage_percent', 0):.1f}%\n"
        )
        description += f"**Errors Found:** {self.stats['errors_found']}\n"
        description += f"**Uptime:** {self.stats['uptime_seconds'] // 60}m {self.stats['uptime_seconds'] % 60}s\n"

        self.teams_notifier.send_alert(
            title=f"{status_emoji} Brute Force Cycle #{self.stats['run_number']} Complete",
            description=description,
            severity=severity,
            category="BRUTE_FORCE_COMPLETED",
            suggested_fix="Review error logs if errors were detected.",
        )

    def run_continuous(
        self, refresh_interval_minutes: int = 60, max_screens_per_cycle: int = 50
    ):
        """
        Run brute force testing continuously.
        Refreshes the browser between cycles to pick up new deployments.

        Args:
            refresh_interval_minutes: Minutes between full refresh cycles
            max_screens_per_cycle: Max screens per exploration cycle
        """
        self._running = True
        self._stop_requested = False

        # Handle shutdown signals
        def signal_handler(sig, frame):
            logger.info("Shutdown signal received")
            self._stop_requested = True

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        self.stats["run_number"] = 0

        while self._running and not self._stop_requested:
            self.stats["run_number"] += 1
            logger.info(f"Starting exploration cycle #{self.stats['run_number']}")

            try:
                # Run exploration
                stats = self.run_exploration(
                    max_screens=max_screens_per_cycle,
                    timeout_minutes=refresh_interval_minutes,
                    resume=True,
                )

                logger.info(f"Cycle complete: {stats}")

                # Wait before next cycle
                if not self._stop_requested:
                    logger.info(
                        f"Waiting {refresh_interval_minutes} minutes before next cycle..."
                    )
                    for _ in range(refresh_interval_minutes * 60):
                        if self._stop_requested:
                            break
                        time.sleep(1)

            except Exception as e:
                logger.error(f"Cycle failed: {e}")
                time.sleep(60)  # Wait before retry

        logger.info("Continuous exploration stopped")

    def stop(self):
        """Request graceful stop"""
        self._stop_requested = True
        self._running = False

    def is_running(self) -> bool:
        """Check if exploration is running"""
        return self._running

    def get_stats(self) -> dict:
        """Get current stats"""
        stats = dict(self.stats)
        stats.update(self.site_map.get_coverage_stats())
        return stats

    def _capture_current_screen(self) -> Optional[str]:
        """Capture and fingerprint current screen"""
        try:
            page = self.browser_manager.page
            viewport = self.browser_manager.get_viewport_size()

            # Capture screenshot
            filepath, base64_data = self.screenshot_handler.capture_state(page, "bf")

            # Read bytes for fingerprinting
            with open(filepath, "rb") as f:
                screenshot_bytes = f.read()

            # Generate fingerprint
            fingerprint = SiteMap.generate_fingerprint(screenshot_bytes)

            # Check if new screen
            if not self.site_map.is_screen_known(fingerprint):
                # Discover elements
                elements = self.element_discovery.discover_elements(
                    base64_data, viewport
                )

                # Add to site map
                self.site_map.add_screen(
                    fingerprint=fingerprint,
                    screenshot_path=filepath,
                    url=page.url,
                    elements=elements,
                )

            self.stats["current_screen"] = fingerprint[:8]
            return fingerprint

        except Exception as e:
            logger.error(f"Failed to capture screen: {e}")
            return None

    def _test_element(self, screen_fp: str, element: InteractiveElement):
        """Test a single element"""
        from src.diagnostics.brute_force_logger import InteractionLog

        page = self.browser_manager.page
        start_url = page.url
        start_time = time.time()

        # Capture before screenshot
        before_path, _ = self.screenshot_handler.capture_state(page, "before")

        try:
            # Click the element
            x, y = element.center
            page.mouse.click(x, y)
            time.sleep(2)  # Wait for response

            # Capture after screenshot
            after_path, after_base64 = self.screenshot_handler.capture_state(
                page, "after"
            )

            # Generate after fingerprint
            with open(after_path, "rb") as f:
                after_bytes = f.read()
            after_fp = SiteMap.generate_fingerprint(after_bytes)

            # Determine result
            if after_fp != screen_fp:
                result = "navigated"
                # Record transition
                self.site_map.add_transition(screen_fp, element.label, after_fp, result)

                # Check if new screen
                if not self.site_map.is_screen_known(after_fp):
                    viewport = self.browser_manager.get_viewport_size()
                    elements = self.element_discovery.discover_elements(
                        after_base64, viewport
                    )
                    self.site_map.add_screen(after_fp, after_path, page.url, elements)

                # Navigate back
                page.go_back()
                time.sleep(1)
            else:
                result = "no_change"
                self.site_map.add_transition(
                    screen_fp, element.label, screen_fp, result
                )

            # Log interaction
            log = InteractionLog(
                run_id=self._current_run_id,
                screen_fingerprint=screen_fp,
                element_label=element.label,
                element_type=element.element_type,
                action="click",
                result=result,
                screenshot_before=before_path,
                screenshot_after=after_path,
                response_time_ms=int((time.time() - start_time) * 1000),
            )
            self.logger.log_interaction(log)

        except Exception as e:
            logger.error(f"Element test failed: {e}")

            # Log error
            log = InteractionLog(
                run_id=self._current_run_id,
                screen_fingerprint=screen_fp,
                element_label=element.label,
                element_type=element.element_type,
                action="click",
                result="error",
                error_details={"message": str(e)},
                screenshot_before=before_path,
                response_time_ms=int((time.time() - start_time) * 1000),
            )
            self.logger.log_interaction(log)

            self.stats["errors_found"] += 1
            self.site_map.mark_screen_has_issues(screen_fp)

            # Send Teams alert for element error
            self.teams_notifier.send_alert(
                title=f"Brute Force Element Error - {self._current_run_id}",
                description=f"Error occurred while testing element '{element.label}' ({element.element_type}).\n\n"
                f"Error: {str(e)}\n"
                f"Screen: {screen_fp[:16]}...\n"
                f"URL: {start_url}\n"
                f"Total Errors This Run: {self.stats['errors_found']}",
                severity="P1",
                category="ELEMENT_TEST_ERROR",
                suggested_fix="Check if element is interactable and page state is stable.",
                screenshot_path=before_path,
                target_url=start_url,
            )

            # Try to recover
            try:
                page.goto(start_url)
                time.sleep(2)
            except:
                pass
