"""
Shared Session Tracking - Used across Dashboard and Test Cases pages
Enables live syncing of test case logs and screenshots between pages
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any

# Base directory for session data
SESSIONS_DIR = Path("screenshots") / ".sessions"

def ensure_dirs():
    """Ensure required directories exist"""
    Path("screenshots").mkdir(exist_ok=True)
    SESSIONS_DIR.mkdir(exist_ok=True)


def get_session_log_file(session_id: str) -> Path:
    """Get the log file path for a specific session"""
    ensure_dirs()
    return SESSIONS_DIR / f"{session_id}_logs.json"


def get_session_status_file(session_id: str) -> Path:
    """Get the status file path for a specific session"""
    ensure_dirs()
    return SESSIONS_DIR / f"{session_id}_status.json"


def get_active_sessions_file() -> Path:
    """Get the file tracking all active sessions"""
    ensure_dirs()
    return SESSIONS_DIR / "active_sessions.json"


def read_active_sessions() -> Dict[str, Dict]:
    """Read all active sessions
    
    Returns:
        Dict mapping session_id to session info (name, start_time, test_case_id)
    """
    try:
        filepath = get_active_sessions_file()
        if filepath.exists():
            with open(filepath, "r") as f:
                return json.load(f)
    except:
        pass
    return {}


def register_session(session_id: str, name: str, test_case_id: Optional[str] = None):
    """Register a new active session"""
    ensure_dirs()
    sessions = read_active_sessions()
    sessions[session_id] = {
        "name": name,
        "start_time": datetime.now().isoformat(),
        "test_case_id": test_case_id,
        "running": True
    }
    try:
        with open(get_active_sessions_file(), "w") as f:
            json.dump(sessions, f)
    except Exception as e:
        print(f"Failed to register session: {e}")


def unregister_session(session_id: str):
    """Mark a session as no longer running"""
    sessions = read_active_sessions()
    if session_id in sessions:
        sessions[session_id]["running"] = False
        sessions[session_id]["end_time"] = datetime.now().isoformat()
        try:
            with open(get_active_sessions_file(), "w") as f:
                json.dump(sessions, f)
        except Exception as e:
            print(f"Failed to unregister session: {e}")


def get_running_sessions() -> Dict[str, Dict]:
    """Get only currently running sessions"""
    sessions = read_active_sessions()
    return {sid: info for sid, info in sessions.items() if info.get("running", False)}


def read_session_logs(session_id: str) -> List[Dict]:
    """Read logs for a specific session"""
    try:
        filepath = get_session_log_file(session_id)
        if filepath.exists():
            with open(filepath, "r") as f:
                return json.load(f)
    except:
        pass
    return []


def write_session_log(session_id: str, message: str, log_type: str = "info", reasoning: str = ""):
    """Write log to a specific session's log file
    
    Args:
        session_id: The session to write logs for
        message: The log message to display
        log_type: Type of log (info, action, success, error, thinking, click, type, scroll, go_back)
        reasoning: Optional AI reasoning/justification for this action
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
    
    entry = {
        "timestamp": timestamp,
        "emoji": emoji,
        "message": message,
        "reasoning": reasoning,
        "type": log_type
    }
    
    logs = read_session_logs(session_id)
    logs.append(entry)
    logs = logs[-100:]  # Keep only last 100
    
    try:
        with open(get_session_log_file(session_id), "w") as f:
            json.dump(logs, f)
    except Exception as e:
        print(f"Failed to write session log: {e}")


def read_session_status(session_id: str) -> Dict:
    """Read status for a specific session"""
    try:
        filepath = get_session_status_file(session_id)
        if filepath.exists():
            with open(filepath, "r") as f:
                return json.load(f)
    except:
        pass
    return {"running": False, "step_count": 0, "issues": []}


def write_session_status(session_id: str, running: bool = None, step_count: int = None, 
                         issues: list = None, screenshots: List[str] = None):
    """Write status for a specific session"""
    ensure_dirs()
    status = read_session_status(session_id)
    
    if running is not None:
        status["running"] = running
    if step_count is not None:
        status["step_count"] = step_count
    if issues is not None:
        status["issues"] = issues
    if screenshots is not None:
        status["screenshots"] = screenshots
    
    try:
        with open(get_session_status_file(session_id), "w") as f:
            json.dump(status, f)
    except Exception as e:
        print(f"Failed to write session status: {e}")


def clear_session_data(session_id: str):
    """Clear all data for a specific session"""
    try:
        log_file = get_session_log_file(session_id)
        if log_file.exists():
            log_file.unlink()
        status_file = get_session_status_file(session_id)
        if status_file.exists():
            status_file.unlink()
    except:
        pass


def clear_all_sessions():
    """Clear all session data and tracking"""
    try:
        active_file = get_active_sessions_file()
        if active_file.exists():
            active_file.unlink()
        # Clear all session files
        if SESSIONS_DIR.exists():
            for f in SESSIONS_DIR.glob("*.json"):
                f.unlink()
    except:
        pass
