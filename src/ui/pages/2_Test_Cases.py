"""
Test Cases Page - Streamlit UI for managing prompt-driven test cases
"""

import streamlit as st
import os
import sys
import json
import time
import threading
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from src.testcases.test_case_model import TestCase, TestCaseResult, TestStatus
from src.testcases.test_case_store import TestCaseStore

# Initialize store
store = TestCaseStore()

# Session state
if "running_test" not in st.session_state:
    st.session_state.running_test = None
if "selected_tests" not in st.session_state:
    st.session_state.selected_tests = set()


def run_test_case(test_case: TestCase, use_browserless: bool = True) -> TestCaseResult:
    """Execute a test case and return result
    
    Args:
        test_case: The test case to run
        use_browserless: Whether to use Docker Browserless for stealth
    """
    from src.core.navigation_engine import NavigationEngine
    from src.ui.shared_session import (
        register_session, unregister_session, write_session_log, 
        write_session_status, clear_session_data
    )
    
    start_time = time.time()
    screenshots = []
    issues = []
    status = TestStatus.ERROR
    error_msg = None
    steps = 0
    
    # Use test case ID as session ID for tracking
    session_id = test_case.id
    
    try:
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            return TestCaseResult.create(
                test_case_id=test_case.id,
                status=TestStatus.ERROR.value,
                steps_taken=0,
                issues_found=[],
                duration_seconds=0,
                error_message="GOOGLE_API_KEY not set"
            )
        
        # Clear previous session data and register new session
        clear_session_data(session_id)
        register_session(session_id, test_case.name, test_case.id)
        write_session_status(session_id, running=True, step_count=0, issues=[])
        write_session_log(session_id, f"Starting test: {test_case.name}", "action")
        write_session_log(session_id, f"Objective: {test_case.objective}", "info")
        browser_mode = "Browserless Docker" if use_browserless else "Local Chromium"
        write_session_log(session_id, f"Browser mode: {browser_mode}", "info")
        
        engine = NavigationEngine(api_key, use_browserless=use_browserless)
        
        # Start session with the test case's objective
        session = engine.start_session(
            url=test_case.target_url,
            objective=test_case.objective,
            max_steps=test_case.max_steps,
            max_errors=3
        )
        
        write_session_log(session_id, f"Navigated to: {test_case.target_url}", "action")
        
        # Run navigation loop
        while session.step_count < test_case.max_steps:
            write_session_status(session_id, step_count=session.step_count + 1)
            
            should_continue = engine.execute_step()
            steps = session.step_count
            
            # Log the action with full reasoning
            if session.actions_taken:
                last_action = session.actions_taken[-1]
                action_type = last_action.action_type
                full_reasoning = last_action.reasoning if last_action.reasoning else "No reasoning provided"
                short_reasoning = full_reasoning[:50] + "..." if len(full_reasoning) > 50 else full_reasoning
                
                if action_type == "click":
                    write_session_log(session_id, f"Clicking: {short_reasoning}", "click", full_reasoning)
                elif action_type == "type":
                    text_typed = last_action.text_to_type or ""
                    write_session_log(session_id, f"Typing: {text_typed[:30]}", "type", full_reasoning)
                elif action_type == "scroll":
                    direction = getattr(last_action, 'scroll_direction', 'down')
                    write_session_log(session_id, f"Scrolling {direction}", "scroll", full_reasoning)
                elif action_type == "go_back":
                    write_session_log(session_id, "Going back", "go_back", full_reasoning)
                elif action_type == "done":
                    write_session_log(session_id, "Objective completed!", "success", full_reasoning)
                elif action_type == "stuck":
                    write_session_log(session_id, "Agent is stuck", "error", full_reasoning)
                else:
                    write_session_log(session_id, f"{action_type}: {short_reasoning}", "thinking", full_reasoning)
            
            if not should_continue:
                break
        
        # Determine status from session state
        state_val = session.state.value if hasattr(session.state, 'value') else str(session.state)
        if state_val == "completed":
            status = TestStatus.PASS
        elif state_val == "stuck":
            status = TestStatus.STUCK
        elif state_val == "max_steps_reached":
            status = TestStatus.TIMEOUT
        else:
            status = TestStatus.FAIL
        
        # Collect issues - serialize properly
        for issue in session.issues_detected:
            if hasattr(issue, 'to_dict'):
                issues.append(issue.to_dict())
            elif hasattr(issue, '__dict__'):
                issue_dict = {}
                for k, v in issue.__dict__.items():
                    if hasattr(v, 'value'):  # Handle enums
                        issue_dict[k] = v.value
                    elif isinstance(v, (str, int, float, bool, type(None))):
                        issue_dict[k] = v
                    else:
                        issue_dict[k] = str(v)
                issues.append(issue_dict)
            else:
                issues.append({"description": str(issue)})
        
        # Collect screenshot paths
        screenshots_dir = Path("screenshots")
        if screenshots_dir.exists():
            screenshots = [str(f) for f in screenshots_dir.glob("*.png")][-5:]
        
        write_session_status(session_id, issues=issues, screenshots=screenshots)
        write_session_log(session_id, f"Test completed: {status.value}", 
                         "success" if status == TestStatus.PASS else "error")
        
        engine.cleanup()
        
    except Exception as e:
        status = TestStatus.ERROR
        error_msg = str(e)
        write_session_log(session_id, f"Error: {str(e)}", "error")
    finally:
        write_session_status(session_id, running=False)
        unregister_session(session_id)
    
    duration = time.time() - start_time
    
    return TestCaseResult.create(
        test_case_id=test_case.id,
        status=status.value,
        steps_taken=steps,
        issues_found=issues,
        duration_seconds=duration,
        screenshots=screenshots,
        error_message=error_msg
    )


# ============================================
# HEADER
# ============================================
st.title("📋 Test Cases")
st.caption("Define testing objectives in natural language")

st.divider()

# ============================================
# CREATE TEST CASE
# ============================================
with st.expander("➕ Create New Test Case", expanded=True):
    form_col1, form_col2 = st.columns([2, 1])
    
    with form_col1:
        tc_name = st.text_input(
            "Test Case Name",
            placeholder="e.g., Login with valid credentials"
        )
        tc_objective = st.text_area(
            "Objective (Natural Language)",
            placeholder="What should the agent try to accomplish?\n\nExample: Navigate to the login page, enter valid credentials, and verify successful login.",
            height=100
        )
    
    with form_col2:
        tc_url = st.text_input(
            "Target URL",
            value=os.getenv("TARGET_STAGING_URL", "https://www.google.com")
        )
        tc_persona = st.selectbox(
            "Persona",
            options=["normal_user", "confused_first_timer", "impatient_user", "elderly_user"]
        )
        tc_max_steps = st.slider("Max Steps", min_value=5, max_value=50, value=30)
        tc_tags = st.text_input("Tags (comma-separated)", placeholder="login, smoke, regression")
        
        # Single shared browserless setting (syncs with saved test cases section)
        if "use_browserless" not in st.session_state:
            st.session_state.use_browserless = True
        use_browserless = st.checkbox(
            "🐳 Docker Browserless",
            value=st.session_state.use_browserless,
            key="create_browserless",
            help="Use local Docker Browserless (ws://localhost:3000) for stealth & bot detection bypass",
            on_change=lambda: setattr(st.session_state, 'use_browserless', st.session_state.create_browserless)
        )
    
    btn_col1, btn_col2, btn_col3 = st.columns([1, 1, 3])
    
    with btn_col1:
        if st.button("💾 Save & Run", type="primary", disabled=not tc_name or not tc_objective):
            tags = [t.strip() for t in tc_tags.split(",") if t.strip()]
            test_case = TestCase.create(
                name=tc_name,
                objective=tc_objective,
                target_url=tc_url,
                persona=tc_persona,
                tags=tags,
                max_steps=tc_max_steps,
                use_browserless=use_browserless
            )
            store.save_test_case(test_case)
            
            with st.spinner(f"Running: {tc_name}..."):
                result = run_test_case(test_case, use_browserless=test_case.use_browserless)
                store.save_result(result)
            
            if result.status == TestStatus.PASS.value:
                st.success(f"✅ Test passed in {result.steps_taken} steps!")
            else:
                st.error(f"❌ Test {result.status}: {result.error_message or 'Check issues'}")
            
            st.rerun()
    
    with btn_col2:
        if st.button("💾 Save for Later", disabled=not tc_name or not tc_objective):
            tags = [t.strip() for t in tc_tags.split(",") if t.strip()]
            test_case = TestCase.create(
                name=tc_name,
                objective=tc_objective,
                target_url=tc_url,
                persona=tc_persona,
                tags=tags,
                max_steps=tc_max_steps,
                use_browserless=use_browserless
            )
            store.save_test_case(test_case)
            st.success(f"Saved: {tc_name} (Browserless: {'Yes' if use_browserless else 'No'})")
            st.rerun()

st.divider()

# ============================================
# SAVED TEST CASES
# ============================================
st.subheader("📁 Saved Test Cases")

# Global settings for running saved tests (synced with create section)
settings_col1, settings_col2 = st.columns([1, 4])
with settings_col1:
    if "use_browserless" not in st.session_state:
        st.session_state.use_browserless = True
    saved_use_browserless = st.checkbox(
        "🐳 Browserless",
        value=st.session_state.use_browserless,
        key="saved_browserless",
        help="Use Docker Browserless for test runs",
        on_change=lambda: setattr(st.session_state, 'use_browserless', st.session_state.saved_browserless)
    )

test_cases = store.list_test_cases()

if not test_cases:
    st.info("No test cases saved yet. Create one above!")
else:
    # Action buttons
    action_col1, action_col2, action_col3 = st.columns([1, 1, 4])
    
    with action_col1:
        if st.button("📥 Export All"):
            data = store.export_all()
            st.download_button(
                label="Download JSON",
                data=json.dumps(data, indent=2),
                file_name="test_cases_export.json",
                mime="application/json"
            )
    
    with action_col2:
        uploaded = st.file_uploader("Import", type="json", label_visibility="collapsed")
        if uploaded:
            data = json.load(uploaded)
            count = store.import_bundle(data)
            st.success(f"Imported {count} test cases")
            st.rerun()
    
    st.markdown("")  # Spacing
    
    # Test cases list - using expanders with inline run button
    for tc in test_cases:
        # Build status indicator
        status_emoji = {
            "PASS": "✅",
            "FAIL": "❌", 
            "STUCK": "🔄",
            "TIMEOUT": "⏱️",
            "ERROR": "⚠️"
        }
        status = status_emoji.get(tc.last_result, "⚪") if tc.last_result else "⚪"
        
        # Build last run text
        if tc.last_run:
            delta = datetime.now() - tc.last_run
            if delta.days > 0:
                last_run_text = f"{delta.days}d ago"
            elif delta.seconds > 3600:
                last_run_text = f"{delta.seconds // 3600}h ago"
            else:
                last_run_text = f"{delta.seconds // 60}m ago"
        else:
            last_run_text = "Never"
        
        # Row with expander and run button side by side
        row_col1, row_col2 = st.columns([10, 1])
        
        with row_col2:
            if st.button("▶️", key=f"run_{tc.id}", help="Run this test", type="primary"):
                with st.spinner("Running..."):
                    # Use the test case's saved browserless setting
                    tc_browserless = getattr(tc, 'use_browserless', True)
                    result = run_test_case(tc, use_browserless=tc_browserless)
                    store.save_result(result)
                st.rerun()
        
        with row_col1:
            with st.expander(f"{status} **{tc.name}** - {last_run_text}", expanded=False):
                # Info row
                st.markdown(f"**Objective:** {tc.objective}")
                
                info_col1, info_col2, info_col3 = st.columns(3)
                with info_col1:
                    st.caption(f"🌐 {tc.target_url}")
                with info_col2:
                    st.caption(f"👤 {tc.persona}")
                with info_col3:
                    st.caption(f"📊 {tc.run_count} runs | Max {tc.max_steps} steps")
                
                if tc.tags:
                    st.markdown(" ".join([f"`{t}`" for t in tc.tags]))
                
                # Show browserless setting
                tc_browserless = getattr(tc, 'use_browserless', True)
                browserless_icon = "🐳" if tc_browserless else "💻"
                st.caption(f"{browserless_icon} {'Docker Browserless' if tc_browserless else 'Local Chromium'}")
                
                st.markdown("---")
                
                # Edit and Delete buttons
                edit_col1, edit_col2, edit_col3 = st.columns([1, 1, 3])
                
                with edit_col1:
                    # Toggle browserless for this test case
                    new_browserless = st.checkbox(
                        "🐳 Browserless",
                        value=tc_browserless,
                        key=f"bl_{tc.id}",
                        help="Toggle Docker Browserless for this test"
                    )
                    if new_browserless != tc_browserless:
                        tc.use_browserless = new_browserless
                        store.save_test_case(tc)
                        st.rerun()
                
                with edit_col2:
                    if st.button("🗑️ Delete", key=f"del_{tc.id}"):
                        store.delete_test_case(tc.id)
                        st.rerun()
                
                # Show run history
                history = store.get_run_history(tc.id)
                if history:
                    st.markdown("**Run History:**")
                    for r in history[:5]:
                        status_icon = status_emoji.get(r.status, "❓")
                        st.markdown(
                            f"- {status_icon} **{r.status}** - "
                            f"{r.timestamp.strftime('%Y-%m-%d %H:%M')} - "
                            f"{r.steps_taken} steps - "
                            f"{r.duration_seconds:.1f}s"
                        )
                        if r.error_message:
                            st.caption(f"  ⚠️ {r.error_message[:100]}")

# ============================================
# FOOTER
# ============================================
st.divider()
st.caption("Phase 5: Prompt-Driven Test Cases | Mystery Shopper")
