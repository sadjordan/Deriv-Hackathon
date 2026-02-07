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


def write_log(message: str, log_type: str = "info"):
    """Write log to file (safe to call from any thread)"""
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
        "scroll": "📜"
    }
    
    emoji = type_emoji.get(log_type, "•")
    entry = f"[{timestamp}] {emoji} {message}"
    
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

# Read current status from file
current_status = read_status()
current_logs = read_logs()

# Auto-refresh every 2 seconds when session is running
if current_status.get("running", False) and HAS_AUTOREFRESH:
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


def run_navigation_session(url: str, persona: str, objective: str, max_steps: int):
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
            
        engine = NavigationEngine(api_key)
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
            
            # Log the action
            if session.actions_taken:
                last_action = session.actions_taken[-1]
                action_type = last_action.action_type
                reasoning = last_action.reasoning[:60] if last_action.reasoning else "..."
                
                if action_type == "click":
                    write_log(f"Clicking: {reasoning}", "click")
                elif action_type == "type":
                    write_log(f"Typing: {last_action.text_to_type}", "type")
                elif action_type == "scroll":
                    write_log("Scrolling page", "scroll")
                elif action_type == "done":
                    write_log("Objective completed!", "success")
                else:
                    write_log(f"{action_type}: {reasoning}", "thinking")
            
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
        st.image(screenshot_path, width=400)
        st.caption(f"Latest: {Path(screenshot_path).name}")
    else:
        st.info("No screenshots yet. Start a session to begin.")

# RIGHT: AI Thought Log
with right_col:
    st.subheader("🧠 AI Thought Process")
    
    # Scrolling log display
    log_container = st.container(height=400)
    with log_container:
        if current_logs:
            # Show logs in reverse order (newest first)
            for entry in reversed(current_logs[-30:]):
                st.text(entry)
        else:
            st.text("Waiting for session to start...")
            st.text("")
            st.text("The AI will show its reasoning here:")
            st.text("• What it sees on screen")
            st.text("• Which element to interact with")
            st.text("• Actions taken (click, type, scroll)")
            st.text("• Any issues detected")

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
                    args=(target_url, persona, objective, max_steps),
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
