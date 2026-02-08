"""
Brute Force Mode - Streamlit UI page for continuous autonomous testing
"""

import streamlit as st
import os
import sys
import threading
import json
import time
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

# Session state
if "bf_running" not in st.session_state:
    st.session_state.bf_running = False
if "bf_engine" not in st.session_state:
    st.session_state.bf_engine = None
if "bf_thread" not in st.session_state:
    st.session_state.bf_thread = None

# Status file for thread communication
STATUS_FILE = Path("brute_force_logs") / ".bf_status.json"
STATUS_FILE.parent.mkdir(exist_ok=True)


def read_status() -> dict:
    """Read brute force status from file"""
    try:
        if STATUS_FILE.exists():
            with open(STATUS_FILE, "r") as f:
                return json.load(f)
    except:
        pass
    return {
        "running": False,
        "screens": 0,
        "elements_tested": 0,
        "total_elements": 0,
        "coverage": 0,
        "errors": 0,
        "uptime": 0,
        "run_number": 0,
        "current_screen": None
    }


def write_status(status: dict):
    """Write status to file"""
    try:
        with open(STATUS_FILE, "w") as f:
            json.dump(status, f)
    except:
        pass


def run_brute_force(target_url: str, refresh_interval: int, max_screens: int):
    """Background thread function for brute force"""
    try:
        from src.core.brute_force_engine import BruteForceEngine
        
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            write_status({"running": False, "error": "GOOGLE_API_KEY not set"})
            return
        
        engine = BruteForceEngine(api_key=api_key, target_url=target_url)
        
        while True:
            # Update status
            status = engine.get_stats()
            status["running"] = True
            write_status(status)
            
            # Run exploration cycle
            engine.run_exploration(
                max_screens=max_screens,
                timeout_minutes=refresh_interval,
                resume=True
            )
            
            # Check if stopped
            if not engine.is_running():
                break
            
            # Update status after cycle
            status = engine.get_stats()
            status["running"] = True
            write_status(status)
            
            # Wait before next cycle
            for _ in range(refresh_interval * 60):
                bf_status = read_status()
                if not bf_status.get("running", True):
                    break
                time.sleep(1)
            
            bf_status = read_status()
            if not bf_status.get("running", True):
                break
    
    except Exception as e:
        write_status({"running": False, "error": str(e)})
    finally:
        status = read_status()
        status["running"] = False
        write_status(status)


# ============================================
# HEADER
# ============================================
st.title("Brute Force Mode")
st.caption("Systematically test every interactive element")

st.divider()

# ============================================
# CONTROLS
# ============================================
status = read_status()
is_running = status.get("running", False)

st.subheader("Controls")

ctrl_col1, ctrl_col2 = st.columns(2)

with ctrl_col1:
    target_url = st.text_input(
        "Target URL",
        value=os.getenv("TARGET_STAGING_URL", "https://www.google.com"),
        disabled=is_running
    )

with ctrl_col2:
    refresh_interval = st.slider(
        "Refresh Interval (minutes)",
        min_value=15,
        max_value=120,
        value=60,
        disabled=is_running,
        help="Time between full exploration cycles"
    )

max_screens = st.slider(
    "Max Screens per Cycle",
    min_value=10,
    max_value=100,
    value=50,
    disabled=is_running
)

btn_col1, btn_col2, btn_col3 = st.columns([1, 1, 4])

with btn_col1:
    if is_running:
        if st.button("⏹️ Stop", type="secondary", use_container_width=True):
            status["running"] = False
            write_status(status)
            st.rerun()
    else:
        if st.button("▶️ Start", type="primary", use_container_width=True):
            # Validate API key
            if not os.getenv("GOOGLE_API_KEY"):
                st.error("⚠️ GOOGLE_API_KEY not set!")
            else:
                # Start background thread
                status["running"] = True
                status["screens"] = 0
                status["elements_tested"] = 0
                write_status(status)
                
                thread = threading.Thread(
                    target=run_brute_force,
                    args=(target_url, refresh_interval, max_screens),
                    daemon=True
                )
                thread.start()
                st.rerun()

with btn_col2:
    if st.button("🔄 Refresh Stats", use_container_width=True):
        st.rerun()

st.divider()

# ============================================
# LIVE STATS
# ============================================
st.subheader("📊 Live Stats")

if is_running:
    st.success("🟢 Running")
else:
    if status.get("error"):
        st.error(f"❌ Error: {status.get('error')}")
    else:
        st.info("⚪ Idle")

# Metrics row
met_col1, met_col2, met_col3, met_col4 = st.columns(4)

with met_col1:
    st.metric("Screens Discovered", status.get("screens_discovered", status.get("screens", 0)))

with met_col2:
    tested = status.get("tested_elements", status.get("elements_tested", 0))
    total = status.get("total_elements", 0)
    st.metric("Elements Tested", f"{tested} / {total}" if total else tested)

with met_col3:
    coverage = status.get("coverage_percent", status.get("coverage", 0))
    st.metric("Coverage", f"{coverage}%")

with met_col4:
    errors = status.get("errors_found", status.get("errors", 0))
    st.metric("Errors Found", errors)

# Second row
met2_col1, met2_col2, met2_col3, met2_col4 = st.columns(4)

with met2_col1:
    run_num = status.get("run_number", 0)
    st.metric("Run #", run_num)

with met2_col2:
    uptime = status.get("uptime_seconds", status.get("uptime", 0))
    if uptime > 3600:
        uptime_str = f"{uptime // 3600:.0f}h {(uptime % 3600) // 60:.0f}m"
    elif uptime > 60:
        uptime_str = f"{uptime // 60:.0f}m"
    else:
        uptime_str = f"{uptime:.0f}s"
    st.metric("Uptime", uptime_str)

with met2_col3:
    current = status.get("current_screen", "-")
    st.metric("Current Screen", current[:8] if current else "-")

with met2_col4:
    screens_issues = status.get("screens_with_issues", 0)
    st.metric("Screens with Issues", screens_issues)

st.divider()

# ============================================
# SITE MAP (Simple View)
# ============================================
st.subheader("🗺️ Site Map")

# Try to load site map
sitemap_file = Path("sitemap") / "sitemap.json"

if sitemap_file.exists():
    try:
        with open(sitemap_file, "r") as f:
            sitemap_data = json.load(f)
        
        screens = sitemap_data.get("screens", {})
        transitions = sitemap_data.get("transitions", [])
        
        if screens:
            st.write(f"**{len(screens)} screens discovered**")
            
            for fp, screen in list(screens.items())[:10]:  # Show first 10
                has_issues = screen.get("has_issues", False)
                tested_count = len(screen.get("tested_elements", []))
                total_count = len(screen.get("elements", []))
                
                icon = "🔴" if has_issues else "🟢"
                coverage = f"{tested_count}/{total_count}"
                
                with st.expander(f"{icon} {fp[:12]}... - {coverage} elements", expanded=False):
                    st.caption(f"URL: {screen.get('url', 'N/A')}")
                    st.caption(f"Discovered: {screen.get('discovered_at', 'N/A')}")
                    
                    if screen.get("elements"):
                        st.write("**Elements:**")
                        for elem in screen["elements"][:10]:
                            tested = "✓" if elem.get("label") in screen.get("tested_elements", []) else "○"
                            st.text(f"  {tested} [{elem.get('type', '?')}] {elem.get('label', 'Unknown')}")
        else:
            st.info("No screens discovered yet. Start exploration to build the site map.")
            
    except Exception as e:
        st.warning(f"Could not load site map: {e}")
else:
    st.info("No site map found. Start exploration to begin mapping.")

st.divider()

# ============================================
# ISSUE FEED
# ============================================
st.subheader("⚠️ Recent Issues")

# Load recent issues from logs
log_dir = Path("brute_force_logs")

if log_dir.exists():
    # Find the most recent run
    run_files = sorted(log_dir.glob("run_*.jsonl"), reverse=True)
    
    if run_files:
        recent_errors = []
        
        for run_file in run_files[:3]:  # Check last 3 runs
            try:
                with open(run_file, "r") as f:
                    for line in f:
                        if line.strip():
                            log = json.loads(line)
                            if log.get("result") in ("error", "crash"):
                                recent_errors.append(log)
            except:
                pass
        
        if recent_errors:
            for error in recent_errors[-10:]:  # Show last 10 errors
                severity = "🔴" if error.get("result") == "crash" else "🟠"
                
                with st.expander(
                    f"{severity} {error.get('element_label', 'Unknown')} - {error.get('result', 'error')}",
                    expanded=False
                ):
                    st.write(f"**Screen:** {error.get('screen_fingerprint', 'N/A')[:12]}...")
                    st.write(f"**Element Type:** {error.get('element_type', 'N/A')}")
                    st.write(f"**Time:** {error.get('timestamp', 'N/A')}")
                    
                    if error.get("error_details"):
                        st.error(f"Details: {error['error_details']}")
        else:
            st.success("✅ No errors found in recent runs")
    else:
        st.info("No run logs yet")
else:
    st.info("No logs found. Start exploration to begin logging.")

# ============================================
# FOOTER
# ============================================
st.divider()
st.caption("Phase 6: Brute Force Mode | Mystery Shopper")

# Auto-refresh when running
if is_running:
    try:
        from streamlit_autorefresh import st_autorefresh
        st_autorefresh(interval=5000, limit=None, key="bf_autorefresh")
    except ImportError:
        st.info("💡 Install `streamlit-autorefresh` for live updates")
