"""
Navigation Engine
Autonomous navigation with integrated issue detection
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
import logging
import time
from datetime import datetime

from src.browser.playwright_manager import BrowserManager
from src.browser.action_executor import ActionExecutor
from src.vision.screenshot_handler import ScreenshotHandler
from src.ai.vision_navigator import GeminiVisionNavigator, NavigationAction
from src.diagnostics.issue_detector import IssueDetector, DetectedIssue

logger = logging.getLogger(__name__)


class NavigationState(Enum):
    """States for the navigation state machine"""
    INITIALIZED = "initialized"
    NAVIGATING = "navigating"
    STUCK = "stuck"
    ERROR = "error"
    COMPLETED = "completed"
    TIMEOUT = "timeout"


@dataclass
class NavigationSession:
    """Tracks a single navigation session"""
    session_id: str
    url: str
    objective: str
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    state: NavigationState = NavigationState.INITIALIZED
    step_count: int = 0
    error_count: int = 0
    stuck_count: int = 0  # Track consecutive stuck responses
    max_errors: int = 3
    max_stuck_retries: int = 3  # Give up after 3 consecutive stuck responses
    actions_taken: List[NavigationAction] = field(default_factory=list)
    screenshots: List[str] = field(default_factory=list)
    state_transitions: List[Dict[str, Any]] = field(default_factory=list)
    completion_reason: Optional[str] = None
    issues_detected: List[Dict[str, Any]] = field(default_factory=list)  # For Phase 3


class NavigationEngine:
    """Core navigation engine for autonomous testing"""
    
    def __init__(self, google_api_key: str, use_browserless: bool = False):
        """
        Initialize the navigation engine
        
        Args:
            google_api_key: Google API key for Gemini
            use_browserless: Whether to use browserless.io cloud browser for stealth/CAPTCHA
        """
        self.use_browserless = use_browserless
        self.browser_manager: Optional[BrowserManager] = None
        self.action_executor: Optional[ActionExecutor] = None
        self.screenshot_handler: Optional[ScreenshotHandler] = None
        self.vision_navigator = GeminiVisionNavigator(google_api_key)
        self.issue_detector = IssueDetector(google_api_key)  # Phase 3: Issue detection
        self.current_session: Optional[NavigationSession] = None
        
        mode = "Browserless.io cloud" if use_browserless else "local browser"
        logger.info(f"NavigationEngine initialized with {mode}")
    
    def _transition_state(self, new_state: NavigationState, reason: str = "") -> None:
        """Transition to a new navigation state"""
        if not self.current_session:
            return
            
        old_state = self.current_session.state
        self.current_session.state = new_state
        
        transition = {
            "from": old_state.value,
            "to": new_state.value,
            "timestamp": datetime.now(),
            "step": self.current_session.step_count,
            "reason": reason
        }
        
        self.current_session.state_transitions.append(transition)
        logger.info(f"State: {old_state.value} → {new_state.value} (step {self.current_session.step_count})")
        if reason:
            logger.info(f"Reason: {reason}")
    
    def start_session(
        self,
        url: str,
        objective: str = "Complete the signup flow",
        max_steps: int = 20,
        max_errors: int = 3
    ) -> NavigationSession:
        """Start a new navigation session"""
        session_id = f"session_{int(time.time())}"
        self.current_session = NavigationSession(
            session_id=session_id,
            url=url,
            objective=objective,
            max_errors=max_errors
        )
        
        # Initialize browser (local or browserless.io cloud)
        self.browser_manager = BrowserManager(
            headless=False if not self.use_browserless else True,
            use_browserless=self.use_browserless,
            solve_captchas=True
        )
        self.browser_manager.start()
        self.action_executor = ActionExecutor(self.browser_manager.page)
        self.screenshot_handler = ScreenshotHandler()
        
        logger.info(f"Started session {session_id}")
        logger.info(f"Objective: {objective}")
        logger.info(f"Max steps: {max_steps}, Max errors: {max_errors}")
        
        # Navigate to URL
        self.browser_manager.navigate(url)
        self._transition_state(NavigationState.NAVIGATING, "Session started")
        
        return self.current_session
    
    def execute_step(self) -> bool:
        """Execute one navigation step. Returns True if should continue."""
        if not self.current_session:
            raise RuntimeError("No active session")
        
        if self.current_session.state not in [NavigationState.NAVIGATING, NavigationState.STUCK]:
            return False
        
        self.current_session.step_count += 1
        step = self.current_session.step_count
        logger.info(f"--- Step {step} ---")
        
        try:
            # 0. Check if page is still alive
            if not self.browser_manager.is_page_alive():
                logger.warning("Page connection lost, attempting to recover...")
                # Try to restart the browser and navigate back
                try:
                    current_url = self.current_session.url
                    self.browser_manager.close()
                    self.browser_manager.start()
                    self.browser_manager.navigate(current_url)
                    logger.info("Browser reconnected successfully")
                except Exception as e:
                    logger.error(f"Failed to recover browser: {e}")
                    self._transition_state(NavigationState.ERROR, f"Browser connection lost: {e}")
                    return False
            
            # 1. Capture screenshot
            screenshot_path, screenshot_b64 = self.screenshot_handler.capture_state(
                page=self.browser_manager.page,
                prefix=f"{self.current_session.session_id}_step_{step}"
            )
            self.current_session.screenshots.append(screenshot_path)
            logger.info(f"Screenshot: {screenshot_path}")
            
            # 2. Get AI decision
            # Build context with step history for better completion detection
            step_history = ""
            if len(self.current_session.actions_taken) > 0:
                recent_actions = self.current_session.actions_taken[-5:]  # Last 5 actions
                step_history = "\n\nPREVIOUS ACTIONS TAKEN:\n"
                for i, prev_action in enumerate(recent_actions):
                    step_history += f"- Step {step - len(recent_actions) + i}: {prev_action.action_type} - {prev_action.reasoning[:50]}\n"
            
            action = self.vision_navigator.get_next_action(
                screenshot_b64,
                f"Objective: {self.current_session.objective}\n\nCurrent Step: {step} of max {self.current_session.step_count + 10}\n{step_history}\n\nAnalyze the current screenshot - has the objective been achieved? If yes, respond with 'done'. Otherwise, what should I do next?"
            )
            
            logger.info(f"AI action: {action.action_type}")
            logger.info(f"Reasoning: {action.reasoning}")
            logger.info(f"Confidence: {action.confidence}")
            
            self.current_session.actions_taken.append(action)
            
            # 3. Check for completion or stuck BEFORE executing
            if action.action_type == "done":
                self._transition_state(NavigationState.COMPLETED, f"Objective completed: {action.reasoning}")
                self.current_session.completion_reason = action.reasoning
                return False
            
            if action.action_type == "stuck":
                self.current_session.stuck_count += 1
                logger.warning(f"Agent reported stuck ({self.current_session.stuck_count}/{self.current_session.max_stuck_retries}): {action.reasoning}")
                
                if self.current_session.stuck_count >= self.current_session.max_stuck_retries:
                    self._transition_state(NavigationState.STUCK, f"Agent stuck after {self.current_session.max_stuck_retries} retries: {action.reasoning}")
                    self.current_session.completion_reason = f"Stuck: {action.reasoning}"
                    return False
                else:
                    # Retry - try scrolling or waiting to get unstuck
                    logger.info(f"Retry {self.current_session.stuck_count}: Attempting recovery by scrolling")
                    self._transition_state(NavigationState.STUCK, f"Stuck retry {self.current_session.stuck_count}")
                    # Try scrolling to reveal more content
                    try:
                        self.action_executor.scroll(direction="up", amount=300)
                        time.sleep(0.5)
                    except:
                        pass
                    return True  # Continue to next step
            
            # 4. Execute action
            success = self._execute_action(action)
            
            if not success:
                self.current_session.error_count += 1
                logger.warning(f"Action failed (errors: {self.current_session.error_count})")
                
                # PHASE 3: Detect issue on failure
                issue = self.issue_detector.detect_issue(
                    description=f"Action failed: {action.reasoning}",
                    step_number=step,
                    screenshot_path=screenshot_path,
                    navigation_state=self.current_session.state.value,
                    error_count=self.current_session.error_count,
                    action_type=action.action_type,
                    screenshot_b64=screenshot_b64
                )
                self.current_session.issues_detected.append(issue)
                logger.info(f"Issue detected: {issue.title}")
                
                if self.current_session.error_count >= self.current_session.max_errors:
                    self._transition_state(
                        NavigationState.ERROR,
                        f"Exceeded error tolerance ({self.current_session.max_errors})"
                    )
                    return False
                else:
                    self._transition_state(NavigationState.STUCK, "Action failed")
                    return True
            
            # 5. Wait for page update
            time.sleep(0.5)
            
            # Successfully navigating - reset stuck counter
            if self.current_session.state == NavigationState.STUCK:
                self._transition_state(NavigationState.NAVIGATING, "Recovered")
            self.current_session.stuck_count = 0  # Reset stuck counter on successful action
            
            return True
            
        except Exception as e:
            logger.error(f"Error in step {step}: {str(e)}", exc_info=True)
            self.current_session.error_count += 1
            
            if self.current_session.error_count >= self.current_session.max_errors:
                self._transition_state(NavigationState.ERROR, f"Exception: {str(e)}")
                return False
            
            return True
    
    def _execute_action(self, action: NavigationAction) -> bool:
        """Execute a navigation action"""
        try:
            if action.action_type in ["click", "tap"]:
                center_x, center_y = self.screenshot_handler.calculate_center(
                    action.bounding_box,
                    self.browser_manager.get_viewport_size()
                )
                
                # Annotate screenshot
                last_screenshot = self.current_session.screenshots[-1]
                self.screenshot_handler.draw_bounding_box(
                    last_screenshot,
                    action.bounding_box,
                    f"{action.action_type}: {action.reasoning[:30]}"
                )
                
                self.action_executor.tap(center_x, center_y)
                logger.info(f"Tapped at ({center_x}, {center_y})")
                return True
                
            elif action.action_type == "type":
                center_x, center_y = self.screenshot_handler.calculate_center(
                    action.bounding_box,
                    self.browser_manager.get_viewport_size()
                )
                
                text = action.text_to_type or ""
                press_enter = getattr(action, 'press_enter', False)
                
                # Use the enhanced type_text method with press_enter support
                success = self.action_executor.type_text(center_x, center_y, text, press_enter=press_enter)
                
                enter_msg = " and pressed Enter" if press_enter else ""
                logger.info(f"Typed: {text}{enter_msg}")
                return success
                
            elif action.action_type == "press_key":
                # Press a specific key (Enter, Tab, Escape, etc.)
                key = getattr(action, 'key_to_press', 'Enter') or 'Enter'
                success = self.action_executor.press_key(key)
                logger.info(f"Pressed key: {key}")
                return success
                
            elif action.action_type == "scroll":
                direction = getattr(action, 'scroll_direction', 'down') or 'down'
                self.action_executor.scroll(direction=direction, amount=500)
                logger.info(f"Scrolled {direction} 500px")
                return True
                
            elif action.action_type == "wait":
                logger.info("Waiting...")
                time.sleep(1.0)
                return True
                
            elif action.action_type == "go_back":
                logger.info("Going back to previous page")
                success = self.action_executor.go_back()
                return success
                
            elif action.action_type == "done":
                logger.info("Objective completed")
                return True
                
            else:
                logger.warning(f"Unknown action: {action.action_type}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to execute action: {str(e)}", exc_info=True)
            return False
    
    def run_session(
        self,
        url: str,
        objective: str = "Complete the signup flow",
        max_steps: int = 20,
        max_errors: int = 3
    ) -> NavigationSession:
        """Run a complete navigation session"""
        session = self.start_session(url, objective, max_steps, max_errors)
        
        while session.step_count < max_steps:
            should_continue = self.execute_step()
            if not should_continue:
                break
        
        # Check for timeout
        if session.step_count >= max_steps and session.state == NavigationState.NAVIGATING:
            self._transition_state(NavigationState.TIMEOUT, f"Reached max steps ({max_steps})")
        
        # Finalize
        session.end_time = datetime.now()
        duration = (session.end_time - session.start_time).total_seconds()
        
        logger.info(f"Session completed: {session.state.value}")
        logger.info(f"Duration: {duration:.1f}s, Steps: {session.step_count}, Errors: {session.error_count}")
        
        return session
    
    def cleanup(self) -> None:
        """Clean up browser resources"""
        if self.browser_manager:
            self.browser_manager.close()
            logger.info("Browser closed")
