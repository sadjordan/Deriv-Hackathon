"""
Mystery Shopper - Main App Entry Point
Multi-page Streamlit application
"""

import streamlit as st

st.set_page_config(
    page_title="Mystery Shopper",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🔍 Autonomous Mystery Shopper")
st.caption("AI-powered mobile app testing with vision navigation")

st.divider()

st.markdown("""
## Welcome!

Use the **sidebar** to navigate between pages:

- **🖥️ Dashboard** - Live monitoring with screenshot viewer and AI thought log
- **📋 Test Cases** - Create and manage prompt-driven test cases

### Quick Start

1. Set your `GOOGLE_API_KEY` environment variable
2. Go to **Dashboard** to start a live session
3. Or go to **Test Cases** to create reusable test objectives

""")

# Show environment status
import os
if os.getenv("GOOGLE_API_KEY"):
    st.success("✅ GOOGLE_API_KEY is configured")
else:
    st.warning("⚠️ GOOGLE_API_KEY not set - add it to your .env file")

if os.getenv("TEAMS_WEBHOOK_URL"):
    st.success("✅ Teams webhook configured")
else:
    st.info("ℹ️ TEAMS_WEBHOOK_URL not set (optional)")

st.divider()
st.caption("Built with Streamlit • Powered by Gemini Flash 2.5 Vision")
