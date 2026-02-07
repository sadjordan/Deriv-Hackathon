"""
Streamlit Dashboard for Autonomous Mystery Shopper
Live monitoring UI with screenshot viewer and AI thought log

NOTE: Session state cannot be accessed from background threads.
We use file-based logging to communicate between the thread and UI.
"""

import streamlit as st
import os
import sys
import time
import threading
import json
from pathlib import Path
from datetime import datetime
import glob
from dotenv import load_dotenv

load_dotenv()

# Add src to path (go up from pages -> ui -> src)
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

# Import shared session tracking
from src.ui.shared_session import (
    read_active_sessions, get_running_sessions, read_session_logs, 
    read_session_status, write_session_log, write_session_status,
    register_session, unregister_session, clear_session_data as clear_shared_session
)

# Try to import autorefresh, fall back to manual refresh
try:
    from streamlit_autorefresh import st_autorefresh
    HAS_AUTOREFRESH = True
except ImportError:
    HAS_AUTOREFRESH = False

# File-based log storage (thread-safe)
LOG_FILE = Path("screenshots") / ".session_logs.json"
STATUS_FILE = Path("screenshots") / ".session_status.json"


def ensure_dirs():
    """Ensure required directories exist"""
    Path("screenshots").mkdir(exist_ok=True)


def read_logs() -> list:
    """Read logs from file (called from UI thread)"""
    try:
        if LOG_FILE.exists():
            with open(LOG_FILE, "r") as f:
                return json.load(f)
    except:
        pass
    return []


def write_log(message: str, log_type: str = "info", reasoning: str = ""):
    """Write log to file (safe to call from any thread)
    
    Args:
        message: The log message to display
        log_type: Type of log (info, action, success, error, thinking, click, type, scroll)
        reasoning: Optional AI reasoning/justification for this action (shown on hover)
    """
    ensure_dirs()
    timestamp = datetime.now().strftime("%H:%M:%S")
    
    type_emoji = {
        "info": "ℹ️",
        "action": "🎯",
        "success": "✅",
        "error": "❌",
        "thinking": "🤔",
        "click": "👆",
        "type": "⌨️",
        "scroll": "📜",
        "go_back": "⬅️"
    }
    
    emoji = type_emoji.get(log_type, "•")
    
    # Store as dict with message and reasoning
    entry = {
        "timestamp": timestamp,
        "emoji": emoji,
        "message": message,
        "reasoning": reasoning,
        "type": log_type
    }
    
    # Read existing logs
    logs = read_logs()
    logs.append(entry)
    
    # Keep only last 100
    logs = logs[-100:]
    
    # Write back
    try:
        with open(LOG_FILE, "w") as f:
            json.dump(logs, f)
    except Exception as e:
        print(f"Failed to write log: {e}")


def read_status() -> dict:
    """Read session status from file"""
    try:
        if STATUS_FILE.exists():
            with open(STATUS_FILE, "r") as f:
                return json.load(f)
    except:
        pass
    return {"running": False, "step_count": 0, "issues": []}


def write_status(running: bool = None, step_count: int = None, issues: list = None):
    """Write session status to file (safe to call from any thread)"""
    ensure_dirs()
    status = read_status()
    
    if running is not None:
        status["running"] = running
    if step_count is not None:
        status["step_count"] = step_count
    if issues is not None:
        status["issues"] = issues
    
    try:
        with open(STATUS_FILE, "w") as f:
            json.dump(status, f)
    except Exception as e:
        print(f"Failed to write status: {e}")


def clear_session_data():
    """Clear all session data files"""
    try:
        if LOG_FILE.exists():
            LOG_FILE.unlink()
        if STATUS_FILE.exists():
            STATUS_FILE.unlink()
    except:
        pass


# Initialize session state for UI-only state
if "ui_running" not in st.session_state:
    st.session_state.ui_running = False
if "selected_session" not in st.session_state:
    st.session_state.selected_session = "dashboard"  # Default to dashboard session

# Get all active sessions (including from Test Cases page)
all_sessions = read_active_sessions()
running_sessions = get_running_sessions()

# Build session options for dropdown - running sessions first
session_options = {}
# Add running sessions first (so they appear at top)
for sid, info in running_sessions.items():
    session_options[sid] = f"🟢 {info.get('name', sid)[:30]}"
# Add dashboard option
session_options["dashboard"] = "🖥️ Dashboard Session"
# Add non-running sessions
for sid, info in all_sessions.items():
    if sid not in running_sessions:
        session_options[sid] = f"⚪ {info.get('name', sid)[:30]}"

# Auto-select first running test case session if available and not manually selected
if running_sessions and st.session_state.selected_session == "dashboard":
    # Auto-switch to first running session
    first_running = list(running_sessions.keys())[0]
    st.session_state.selected_session = first_running

# Read current status and logs based on selected session
selected_session_id = st.session_state.selected_session
if selected_session_id == "dashboard":
    current_status = read_status()
    current_logs = read_logs()
elif selected_session_id in all_sessions or selected_session_id in running_sessions:
    current_status = read_session_status(selected_session_id)
    current_logs = read_session_logs(selected_session_id)
else:
    # Session no longer exists, fall back to dashboard
    st.session_state.selected_session = "dashboard"
    selected_session_id = "dashboard"
    current_status = read_status()
    current_logs = read_logs()

# Auto-refresh every 2 seconds when any session is running
any_running = current_status.get("running", False) or len(running_sessions) > 0
if any_running and HAS_AUTOREFRESH:
    st_autorefresh(interval=2000, limit=None, key="autorefresh")


def get_latest_screenshot() -> str:
    """Get the most recent screenshot from the screenshots directory"""
    screenshots_dir = Path("screenshots")
    if not screenshots_dir.exists():
        return None
    
    files = [f for f in screenshots_dir.glob("*.png") if not f.name.startswith(".")]
    if not files:
        return None
    
    return str(max(files, key=os.path.getctime))


def run_navigation_session(url: str, persona: str, objective: str, max_steps: int, use_browserless: bool = False):
    """Run navigation in background thread"""
    try:
        from src.core.navigation_engine import NavigationEngine
        from src.alerting.teams_notifier import TeamsNotifier
        
        write_status(running=True, step_count=0, issues=[])
        write_log(f"Starting session with persona: {persona}", "action")
        write_log(f"Objective: {objective}", "info")
        
        # Initialize engine
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            write_log("ERROR: GOOGLE_API_KEY not set!", "error")
            write_status(running=False)
            return
            
        engine = NavigationEngine(api_key, use_browserless=use_browserless)
        notifier = TeamsNotifier()
        
        # Start session
        session = engine.start_session(
            url=url,
            objective=objective,
            max_steps=max_steps,
            max_errors=3
        )
        
        write_log(f"Navigated to: {url}", "action")
        
        # Run navigation loop
        status = read_status()
        while session.step_count < max_steps and status.get("running", True):
            write_status(step_count=session.step_count + 1)
            
            should_continue = engine.execute_step()
            
            # Log the action with full reasoning
            if session.actions_taken:
                last_action = session.actions_taken[-1]
                action_type = last_action.action_type
                full_reasoning = last_action.reasoning if last_action.reasoning else "No reasoning provided"
                short_reasoning = full_reasoning[:50] + "..." if len(full_reasoning) > 50 else full_reasoning
                
                if action_type == "click":
                    write_log(f"Clicking: {short_reasoning}", "click", full_reasoning)
                elif action_type == "type":
                    text_typed = last_action.text_to_type or ""
                    write_log(f"Typing: {text_typed[:30]}", "type", full_reasoning)
                elif action_type == "scroll":
                    direction = getattr(last_action, 'scroll_direction', 'down')
                    write_log(f"Scrolling {direction}", "scroll", full_reasoning)
                elif action_type == "go_back":
                    write_log("Going back", "go_back", full_reasoning)
                elif action_type == "done":
                    write_log("Objective completed!", "success", full_reasoning)
                elif action_type == "stuck":
                    write_log("Agent is stuck", "error", full_reasoning)
                else:
                    write_log(f"{action_type}: {short_reasoning}", "thinking", full_reasoning)
            
            if not should_continue:
                break
            
            # Re-read status to check if stopped
            status = read_status()
        
        # Extract issues
        issues = [
            {
                "title": issue.title if hasattr(issue, 'title') else str(issue.get('title', 'Issue')),
                "description": issue.description if hasattr(issue, 'description') else str(issue.get('description', '')),
                "severity": issue.severity if hasattr(issue, 'severity') else str(issue.get('severity', 'P2')),
                "category": issue.category.value if hasattr(issue, 'category') and hasattr(issue.category, 'value') else str(issue.get('category', 'Unknown')),
                "suggested_fix": issue.root_cause if hasattr(issue, 'root_cause') else str(issue.get('suggested_fix', ''))
            }
            for issue in session.issues_detected
        ]
        write_status(issues=issues)
        
        # Log results
        state_value = session.state.value if hasattr(session.state, 'value') else str(session.state)
        write_log(f"Session completed: {state_value}", 
                "success" if state_value == "completed" else "error")
        
        # Send Teams alerts for any issues
        for issue in issues:
            if issue.get('severity') in ['P0', 'P1']:
                notifier.send_issue_alert(issue)
                write_log(f"Sent Teams alert for {issue.get('severity')} issue", "info")
        
        # Cleanup
        engine.cleanup()
        
    except Exception as e:
        write_log(f"Session error: {str(e)}", "error")
        import traceback
        write_log(traceback.format_exc()[:200], "error")
    finally:
        write_status(running=False)


# ============================================
# HEADER
# ============================================
st.title("🔍 Autonomous Mystery Shopper")
st.caption("AI-powered mobile app testing with vision navigation")

# Session selector (if there are multiple sessions)
if len(session_options) > 1:
    selected = st.selectbox(
        "📋 Active Session",
        options=list(session_options.keys()),
        format_func=lambda x: session_options[x],
        index=list(session_options.keys()).index(selected_session_id) if selected_session_id in session_options else 0,
        key="session_selector"
    )
    if selected != st.session_state.selected_session:
        st.session_state.selected_session = selected
        st.rerun()

# Status row
status_col1, status_col2, status_col3, status_col4 = st.columns([1, 1, 1, 1])

with status_col1:
    if current_status.get("running", False):
        st.success("🟢 Running")
    else:
        st.info("⚪ Idle")

with status_col2:
    st.metric("Steps", current_status.get("step_count", 0))

with status_col3:
    st.metric("Issues", len(current_status.get("issues", [])))

with status_col4:
    if st.button("🔄 Refresh"):
        st.rerun()

st.divider()

# ============================================
# MAIN LAYOUT
# ============================================
left_col, right_col = st.columns([6, 4])

# LEFT: Screenshot Viewer
with left_col:
    st.subheader("📸 Live Screenshot")
    
    screenshot_path = get_latest_screenshot()
    if screenshot_path:
        try:
            st.image(screenshot_path, width=400)
            st.caption(f"Latest: {Path(screenshot_path).name}")
        except Exception as e:
            st.error(f"Error loading screenshot: {e}")
            st.info("Waiting for next valid screenshot...")
    else:
        st.info("No screenshots yet. Start a session to begin.")

# RIGHT: AI Thought Log
with right_col:
    st.subheader("🧠 AI Thought Process")
    st.caption("💡 Hover over ℹ️ icons to see full AI reasoning")
    
    # Scrolling log display
    log_container = st.container(height=400)
    with log_container:
        if current_logs:
            # Show logs in reverse order (newest first)
            for entry in reversed(current_logs[-30:]):
                # Handle both old string format and new dict format
                if isinstance(entry, dict):
                    timestamp = entry.get("timestamp", "")
                    emoji = entry.get("emoji", "•")
                    message = entry.get("message", "")
                    reasoning = entry.get("reasoning", "")
                    
                    # Create columns for log entry + info button
                    if reasoning:
                        col1, col2 = st.columns([9, 1])
                        with col1:
                            st.text(f"[{timestamp}] {emoji} {message}")
                        with col2:
                            st.markdown(
                                f'<span title="{reasoning}" style="cursor:help;">ℹ️</span>',
                                unsafe_allow_html=True
                            )
                    else:
                        st.text(f"[{timestamp}] {emoji} {message}")
                else:
                    # Old string format (backwards compatibility)
                    st.text(entry)
        else:
            st.text("Waiting for session to start...")
            st.text("")
            st.text("The AI will show its reasoning here:")
            st.text("• What it sees on screen")
            st.text("• Which element to interact with")
            st.text("• Actions taken (click, type, scroll)")
            st.text("• Hover ℹ️ for full AI reasoning")

st.divider()

# ============================================
# CONTROLS
# ============================================
st.subheader("⚙️ Session Controls")

is_running = current_status.get("running", False)

ctrl_col1, ctrl_col2 = st.columns([3, 1])

with ctrl_col1:
    target_url = st.text_input(
        "Target URL",
        value=os.getenv("TARGET_STAGING_URL", "https://www.google.com"),
        disabled=is_running,
        help="The URL to start testing from"
    )

ctrl_col3, ctrl_col4, ctrl_col5 = st.columns([2, 2, 1])

with ctrl_col3:
    persona = st.selectbox(
        "Persona",
        options=[
            "normal_user",
            "confused_first_timer",
            "impatient_user",
            "elderly_user"
        ],
        disabled=is_running,
        help="User persona affects AI behavior and hesitation"
    )

with ctrl_col4:
    objective = st.text_input(
        "Objective",
        value="Complete the signup flow",
        disabled=is_running,
        help="What should the AI try to accomplish?"
    )

with ctrl_col5:
    max_steps = st.number_input(
        "Max Steps",
        min_value=5,
        max_value=50,
        value=20,
        disabled=is_running
    )

# Browserless toggle (new row)
browserless_col1, browserless_col2 = st.columns([1, 5])
with browserless_col1:
    use_browserless = st.checkbox(
        "🐳 Docker Browserless",
        value=True,
        disabled=is_running,
        help="Use local Docker Browserless (ws://localhost:3000) for stealth & bot detection bypass"
    )

# Start/Stop buttons
btn_col1, btn_col2, btn_col3 = st.columns([1, 1, 4])

with btn_col1:
    if is_running:
        if st.button("⏹️ Stop", type="secondary", use_container_width=True):
            write_status(running=False)
            write_log("Session stopped by user", "action")
            st.rerun()
    else:
        if st.button("▶️ Start Session", type="primary", use_container_width=True):
            # Validate API key
            if not os.getenv("GOOGLE_API_KEY"):
                st.error("⚠️ GOOGLE_API_KEY environment variable not set!")
            else:
                # Clear previous session data
                clear_session_data()
                write_status(running=True, step_count=0, issues=[])
                
                # Start background thread
                thread = threading.Thread(
                    target=run_navigation_session,
                    args=(target_url, persona, objective, max_steps, use_browserless),
                    daemon=True
                )
                thread.start()
                
                st.rerun()

with btn_col2:
    if st.button("🗑️ Clear Logs", use_container_width=True):
        clear_session_data()
        st.rerun()

# ============================================
# ISSUES PANEL (if any)
# ============================================
issues = current_status.get("issues", [])
if issues:
    st.divider()
    st.subheader("⚠️ Detected Issues")
    
    for i, issue in enumerate(issues):
        severity = issue.get('severity', 'P2')
        severity_colors = {"P0": "🔴", "P1": "🟠", "P2": "🟡", "P3": "🟢"}
        emoji = severity_colors.get(severity, "🟡")
        
        with st.expander(f"{emoji} {issue.get('title', 'Issue')} ({severity})"):
            st.write(f"**Category:** {issue.get('category', 'Unknown')}")
            st.write(f"**Description:** {issue.get('description', 'No description')}")
            if issue.get('suggested_fix'):
                st.success(f"**Suggested Fix:** {issue.get('suggested_fix')}")

# ============================================
# FOOTER
# ============================================
st.divider()
st.caption("Built with Streamlit • Powered by Gemini Flash 2.5 Vision • Phase 4 MVP")
