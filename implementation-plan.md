# Autonomous Mystery Shopper - Implementation Plan
**Project Duration:** 14 Hours  
**Last Updated:** February 7, 2026

---

## 📋 Project Overview

Build an AI-powered agent that autonomously navigates mobile signup flows using **vision-only** navigation, detects UX friction points, and reports issues to Microsoft Teams with actionable insights.

### Core Technology Stack
- **Runtime:** Python 3.10+
- **Browser Automation:** Playwright (Sync API) with iPhone 13 emulation
- **AI Engine:** Google Gemini Flash 2.5 with Vision capabilities
- **Dashboard:** Streamlit for live monitoring
- **Alerting:** Microsoft Teams (Webhooks via Adaptive Cards)

### Critical Design Constraints
✅ **Vision-First Navigation:** No CSS selectors, XPaths, or DOM inspection  
✅ **Mobile-Only:** iPhone 13 viewport emulation  
✅ **Staging Environment:** Hardcoded target URL  
✅ **Live Alerting:** Real-time Microsoft Teams notifications with screenshots  

---

## 🏗️ Phase 1: Vision-to-Action Loop (Foundation)
**Duration:** 2.5 hours  
**Goal:** Prove the agent can interpret screenshots and execute coordinate-based actions

### Tasks

#### 1.1 Environment Setup (30 min)
- [ ] Create Python virtual environment (`venv`)
- [ ] Install dependencies:
  ```
  playwright==1.40.0
  google-generativeai==0.3.2
  streamlit==1.30.0
  pymsteams==0.2.2
  pillow==10.1.0
  python-dotenv==1.0.0
  ```
- [ ] Configure Playwright: `playwright install chromium`
- [ ] Create `.env` file with:
  - `GOOGLE_API_KEY`
  - `TEAMS_WEBHOOK_URL`
  - `TARGET_STAGING_URL`
- [ ] Create `.env.example` template

#### 1.2 Playwright Mobile Initialization (20 min)
- [ ] Create `src/browser/playwright_manager.py`
- [ ] Implement `BrowserManager` class:
  - [ ] Initialize sync Playwright
  - [ ] Configure iPhone 13 device emulation
  - [ ] Set user agent and viewport (390x844)
  - [ ] Enable network interception hooks
- [ ] Add context manager support (`__enter__`, `__exit__`)

#### 1.3 Screenshot Capture System (30 min)
- [ ] Create `src/vision/screenshot_handler.py`
- [ ] Implement `capture_state()` function:
  - [ ] Take full-page screenshot
  - [ ] Convert to base64 encoded string
  - [ ] Save timestamped copy to `screenshots/` directory
  - [ ] Return both file path and base64 string
- [ ] Add overlay drawing function for bounding boxes (using Pillow)

#### 1.4 Gemini Vision Integration (45 min)
- [ ] Create `src/ai/vision_navigator.py`
- [ ] Implement `get_next_action(screenshot_base64, objective, persona)`:
  - [ ] Construct system prompt for coordinate extraction
  - [ ] Send image + objective to Gemini Flash 2.5 Vision API
  - [ ] Parse response for bounding box `[ymin, xmin, ymax, xmax]` (0-1000 scale)
  - [ ] Convert to absolute pixel coordinates (x, y)
  - [ ] Handle API errors and retries (3 attempts)
  - [ ] Configure response format for JSON mode (structured output)
- [ ] Create prompt templates:
  - [ ] Navigation prompt
  - [ ] Diagnosis prompt (for Phase 3)

#### 1.5 Action Executor (30 min)
- [ ] Create `src/browser/action_executor.py`
- [ ] Implement action types:
  - [ ] `click(x, y)` - Tap at coordinates
  - [ ] `type_text(x, y, text)` - Click then type
  - [ ] `scroll(direction, amount)` - Vertical scroll
  - [ ] `wait(seconds)` - Explicit wait
- [ ] Add action validation (check coordinates are within viewport)

#### 1.6 Proof-of-Concept Test (25 min)
- [ ] Create `tests/test_vision_navigation.py`
- [ ] Write test: Navigate to Google.com and search "Hello World"
  - [ ] Open Google in mobile view
  - [ ] Use vision to locate search bar
  - [ ] Click and type query
  - [ ] Verify results page loads
- [ ] Document test results in `TESTING.md`

**Phase 1 Deliverables:**
- ✅ Working vision-to-coordinate pipeline
- ✅ Screenshot capture with overlays
- ✅ Successful Google.com navigation test

---

## 🧠 Phase 2: Confused User Simulation (Intelligence Layer)
**Duration:** 2.5 hours  
**Goal:** Implement autonomous navigation loop with human-like decision making

### Tasks

#### 2.1 Persona System (30 min)
- [ ] Create `src/personas/user_personas.py`
- [ ] Define persona configurations:
  ```python
  PERSONAS = {
      "confused_first_timer": {
          "system_prompt": "You are a confused first-time user...",
          "click_hesitation": 2.0,  # seconds
          "error_tolerance": 1
      },
      "impatient_user": {...},
      "elderly_user": {...}
  }
  ```
- [ ] Add persona selection logic to navigation prompts

#### 2.2 Navigation State Machine (45 min)
- [ ] Create `src/core/navigation_engine.py`
- [ ] Implement `NavigationEngine` class with states:
  - [ ] `INITIALIZED` - Starting state
  - [ ] `NAVIGATING` - Active navigation
  - [ ] `STUCK` - No progress detected
  - [ ] `ERROR` - Critical failure
  - [ ] `COMPLETED` - Goal achieved
- [ ] Add state transition logging

#### 2.3 Main Navigation Loop (60 min)
- [ ] Implement `run_session(url, persona, max_steps=20)`:
  - [ ] Load target URL
  - [ ] **Loop:**
    1. Capture screenshot
    2. Send to Gemini with objective
    3. Parse and validate action
    4. Execute action
    5. Wait for page update (2-3 seconds)
    6. Compare before/after screenshots (pixel diff)
    7. If no change detected → increment retry counter
    8. If retry > 2 → Mark as STUCK
  - [ ] Log each step with timestamp
- [ ] Add screenshot comparison function (using Pillow)

#### 2.4 Input Field Detection (30 min)
- [ ] Enhance action executor for form inputs:
  - [ ] Detect input field type (email, password, text)
  - [ ] Generate appropriate test data:
    - Email: `testuser_{timestamp}@example.com`
    - Password: Random secure string
    - Phone: Valid format based on country detection
  - [ ] Add validation for successful input

#### 2.5 Progress Verification (15 min)
- [ ] Create `src/utils/progress_detector.py`
- [ ] Implement change detection:
  - [ ] Hash-based screenshot comparison
  - [ ] URL change detection
  - [ ] Network activity monitoring
- [ ] Define "stuck" criteria (no change after 2 attempts)

#### 2.6 Integration Test (20 min)
- [ ] Create `tests/test_signup_flow.py`
- [ ] Test: Navigate target staging signup for 3+ steps
- [ ] Verify:
  - [ ] Each step is logged
  - [ ] Form inputs are filled correctly
  - [ ] Progress is detected between steps
- [ ] Document test results

**Phase 2 Deliverables:**
- ✅ Autonomous navigation loop
- ✅ Persona-driven decision making
- ✅ Form input handling
- ✅ 3-step signup flow completion

---

## 🔍 Phase 3: Diagnosis & Severity Scoring (Intelligence)
**Duration:** 2.5 hours  
**Goal:** Detect failures and provide actionable diagnostic reports

### Tasks

#### 3.1 Failure Detection System (30 min)
- [ ] Create `src/diagnostics/failure_detector.py`
- [ ] Implement failure triggers:
  - [ ] Navigation stuck (2+ retries with no progress)
  - [ ] Visual error indicators (Gemini detects error message)
  - [ ] Network error correlation (API failure)
  - [ ] Timeout exceeded (>20 steps)
- [ ] Add failure state capture (screenshot + logs)

#### 3.2 Network Listener Integration (45 min)
- [ ] Create `src/browser/network_monitor.py`
- [ ] Attach Playwright network listener:
  - [ ] Capture all HTTP requests/responses
  - [ ] Filter for 4xx/5xx status codes
  - [ ] Log API endpoint, status, timing
  - [ ] Correlate with current screenshot timestamp
- [ ] Store network logs in `NetworkLog` data class

#### 3.3 AI-Powered Diagnosis (60 min)
- [ ] Create `src/diagnostics/issue_analyzer.py`
- [ ] Implement `diagnose_failure(screenshot, network_logs, context)`:
  - [ ] Send failure screenshot to Gemini Flash 2.5
  - [ ] Prompt: "Analyze this failure. Categorize as:
    - **Server Error** (500, 503, API down)
    - **Client Error** (400, 404, invalid input)
    - **UI Glitch** (overlapping elements, broken layout)
    - **Copy Ambiguity** (unclear instructions, missing labels)
    - **Unresponsive Element** (click has no effect)
  - [ ] Request structured JSON response using JSON mode:
    ```json
    {
      "category": "UI Glitch",
      "description": "Submit button is obscured by footer",
      "severity": "P1",
      "suggested_fix": "Adjust z-index of footer"
    }
    ```
  - [ ] Parse and validate response

#### 3.4 Severity Scoring System (20 min)
- [ ] Define severity matrix:
  - **P0 (Critical):** Complete flow blocker, affects all users
  - **P1 (High):** Major friction, affects >50% of users
  - **P2 (Medium):** Moderate issue, workaround exists
  - **P3 (Low):** Minor cosmetic issue
- [ ] Implement `calculate_severity(category, impact_score)` logic
- [ ] Add severity to diagnostic report

#### 3.5 Screenshot Annotation (25 min)
- [ ] Create `src/vision/annotator.py`
- [ ] Implement annotation features:
  - [ ] Draw red box around problematic element
  - [ ] Add text label with issue description
  - [ ] Highlight error messages
  - [ ] Save annotated screenshot
- [ ] Use for Teams message attachments

#### 3.6 Diagnostic Test (20 min)
- [ ] Manually inject test failures:
  - [ ] Mock API 500 error
  - [ ] Create overlapping UI elements
  - [ ] Test ambiguous button text
- [ ] Verify diagnosis accuracy and severity assignment
- [ ] Document test results

**Phase 3 Deliverables:**
- ✅ Multi-vector failure detection
- ✅ AI-powered issue categorization
- ✅ Network error correlation
- ✅ Annotated failure screenshots

---

## 🎯 Phase 4: Interface & Escalation (Delivery)
**Duration:** 2.5 hours  
**Goal:** Build user-facing dashboard and Microsoft Teams integration

### Tasks

#### 4.1 Microsoft Teams Integration (45 min)
- [ ] Create `src/alerting/teams_notifier.py`
- [ ] Implement `send_alert(diagnosis, screenshot_path, severity)`:
  - [ ] Build Adaptive Card with severity-based theme color:
    - P0: 🔴 Red (#FF0000)
    - P1: 🟠 Orange (#FF8C00)
    - P2: 🟡 Yellow (#FFD700)
    - P3: 🟢 Green (#32CD32)
  - [ ] Card sections:
    - **Header:** Severity badge + Issue category
    - **Body:** Description, timestamp, target URL
    - **Facts:** Network logs (if applicable), suggested fix
    - **Image:** Annotated screenshot (inline or attached)
    - **Actions:** "View Dashboard" button
  - [ ] Use `pymsteams` to post card to webhook
- [ ] Test webhook delivery to Teams channel

#### 4.2 Streamlit Dashboard - Layout (30 min)
- [ ] Create `src/ui/dashboard.py`
- [ ] Build layout:
  - **Header:** Project title, status indicator
  - **Left Column (60%):** 
    - Live screenshot viewer
    - Bounding box overlay visualization
  - **Right Column (40%):**
    - AI thought process log (scrolling)
    - Current step indicator
    - Failure alerts
  - **Bottom Controls:**
    - "Start Simulation" button
    - Persona dropdown selector
    - Target URL input (read-only)

#### 4.3 Real-Time Screenshot Display (30 min)
- [ ] Implement live image updates:
  - [ ] Use `st.image()` with auto-refresh
  - [ ] Display latest screenshot from `screenshots/` directory
  - [ ] Show bounding box overlays from last action
  - [ ] Add zoom controls for mobile viewport
- [ ] Update every 2 seconds during active session

#### 4.4 AI Thought Process Terminal (25 min)
- [ ] Create scrolling text log display:
  - [ ] Stream AI reasoning from Gemini responses
  - [ ] Format: `[12:34:56] 🤔 I see a button labeled "Next". Clicking at (195, 420)...`
  - [ ] Color-code by action type:
    - Navigation: Blue
    - Input: Green
    - Error: Red
  - [ ] Auto-scroll to latest entry
- [ ] Use `st.text_area()` or `st.markdown()` with custom CSS

#### 4.5 Session Controls (20 min)
- [ ] Implement start/stop functionality:
  - [ ] "Start Simulation" → Launch `run_session()` in thread
  - [ ] Display real-time progress
  - [ ] "Stop" button to cancel session
  - [ ] Session status: Running / Stuck / Completed / Failed
- [ ] Add persona selector with descriptions
- [ ] Validate inputs before starting

#### 4.6 End-to-End Test & Polish (30 min)
- [ ] Run full simulation:
  1. Launch Streamlit: `streamlit run src/ui/dashboard.py`
  2. Select "Confused First-Timer" persona
  3. Click "Start Simulation"
  4. Observe live navigation in UI
  5. Trigger failure (or wait for natural friction)
  6. Verify Teams alert delivery
- [ ] Performance check:
  - [ ] Ensure UI doesn't freeze during navigation
  - [ ] Screenshot updates appear within 2 seconds
  - [ ] Network logs are captured correctly
- [ ] Add error handling for edge cases
- [ ] Update README.md with usage instructions

**Phase 4 Deliverables:**
- ✅ Functional Microsoft Teams alerting with Adaptive Cards
- ✅ Live Streamlit dashboard
- ✅ Complete end-to-end demo
- ✅ Documentation

---

## 🎯 Phase 5: Prompt-Driven Test Cases (User-Defined Objectives)
**Duration:** 2 hours  
**Goal:** Let users define testing objectives in natural language and save them as reusable test cases

### Concept
Instead of only running pre-configured signup flows, users type a plain-English objective like:
- *"Try and buy an item"*
- *"Reset my password using email"*
- *"Add 3 items to cart and apply a discount code"*

The LLM receives this as its mission and autonomously figures out how to accomplish it, reporting friction along the way.

### Tasks

#### 5.1 Test Case Data Model (20 min)
- [ ] Create `src/testcases/test_case_model.py`
- [ ] Define `TestCase` dataclass:
  ```python
  @dataclass
  class TestCase:
      id: str                    # UUID
      name: str                  # Human-readable label
      objective: str             # Natural language prompt
      target_url: str            # Starting URL
      persona: str               # Persona key to use
      created_at: datetime
      last_run: Optional[datetime]
      run_count: int
      last_result: Optional[str] # PASS / FAIL / STUCK
      tags: List[str]            # e.g. ["checkout", "regression"]
      max_steps: int             # Step limit (default: 30)
  ```
- [ ] Define `TestCaseResult` dataclass for run history:
  ```python
  @dataclass
  class TestCaseResult:
      test_case_id: str
      run_id: str
      timestamp: datetime
      status: str                # PASS / FAIL / STUCK
      steps_taken: int
      issues_found: List[dict]   # Diagnosis reports
      duration_seconds: float
      screenshots: List[str]     # Paths to key screenshots
  ```

#### 5.2 Test Case Storage (25 min)
- [ ] Create `src/testcases/test_case_store.py`
- [ ] Implement JSON-file-based persistence:
  - [ ] `save_test_case(test_case)` → writes to `testcases/saved/{id}.json`
  - [ ] `load_test_case(id)` → reads and deserializes
  - [ ] `list_test_cases()` → returns all saved test cases
  - [ ] `delete_test_case(id)` → removes from disk
  - [ ] `save_result(result)` → appends to `testcases/results/{test_case_id}/`
  - [ ] `get_run_history(test_case_id)` → list past results
- [ ] Auto-create directory structure on first use

#### 5.3 Objective-Driven Navigation (30 min)
- [ ] Update `NavigationEngine` to accept dynamic objectives:
  - [ ] New method: `run_objective(url, objective, persona, max_steps)`
  - [ ] Modify LLM system prompt to include user's objective:
    ```
    "Your mission: {objective}
     Navigate the app to accomplish this goal.
     At each step, describe what you see and what action you'll take next.
     If you believe the objective is complete, respond with ACTION: DONE.
     If you're stuck, respond with ACTION: STUCK and explain why."
    ```
  - [ ] Add completion detection: LLM signals `DONE` when objective is met
  - [ ] Add step budget enforcement (stop after `max_steps`)
- [ ] Return `TestCaseResult` at end of run

#### 5.4 Streamlit Test Case Manager UI (30 min)
- [ ] Add new page/tab to dashboard: **"Test Cases"**
- [ ] **Create Test Case panel:**
  - [ ] Text input: "What should the agent try to do?"
  - [ ] Name field for the test case
  - [ ] Persona selector dropdown
  - [ ] Tags input (comma-separated)
  - [ ] Max steps slider (5-50, default 30)
  - [ ] "Save & Run" / "Save for Later" buttons
- [ ] **Saved Test Cases panel:**
  - [ ] Table listing all saved test cases:
    - Name | Objective | Last Run | Result | Run Count
  - [ ] Actions per row: ▶ Run | ✏️ Edit | 🗑️ Delete | 📊 History
  - [ ] Batch run: Select multiple + "Run All"
- [ ] **Run History panel:**
  - [ ] Expandable view per test case showing past runs
  - [ ] Status badges (PASS/FAIL/STUCK)
  - [ ] Link to screenshots from each run

#### 5.5 Test Case Import/Export (15 min)
- [ ] Implement export: Download test cases as JSON bundle
- [ ] Implement import: Upload JSON file to add test cases
- [ ] Enable sharing test suites across team members

**Phase 5 Deliverables:**
- ✅ Users can define test objectives in natural language
- ✅ Test cases are saved and reusable
- ✅ Run history with pass/fail tracking
- ✅ UI for managing and re-running test cases

---

## 🔨 Phase 6: Brute Force Mode (Continuous Autonomous Testing)
**Duration:** 2 hours  
**Goal:** Systematically explore every interactive element on the app, running 24/7

### Concept
Unlike the objective-driven mode, **Brute Force Mode** has no specific goal. It:
1. Starts at the target URL
2. Identifies every clickable/interactive element on the current screen
3. Systematically interacts with each one
4. Records the result (navigation change, error, crash, nothing)
5. Builds a **site map** of discovered screens
6. After exhausting the current screen, moves to the next unvisited screen
7. Refreshes the app between full runs to pick up new deployments
8. Runs indefinitely until stopped

### Tasks

#### 6.1 Element Discovery System (30 min)
- [ ] Create `src/core/element_discovery.py`
- [ ] Implement `discover_elements(screenshot_base64)`:
  - [ ] Send screenshot to Gemini with prompt:
    ```
    "Identify ALL interactive elements on this screen.
     For each element, return:
     - label: text/description of the element
     - type: button | link | input | dropdown | toggle | tab | other
     - bounding_box: [ymin, xmin, ymax, xmax] (0-1000 scale)
     - priority: high | medium | low (based on prominence)
     Return as a JSON array."
    ```
  - [ ] Use Gemini's JSON mode for structured response
  - [ ] Parse and validate response
  - [ ] Deduplicate elements across screenshots
- [ ] Create `InteractiveElement` dataclass

#### 6.2 Screen Fingerprinting & Site Map (30 min)
- [ ] Create `src/core/site_mapper.py`
- [ ] Implement screen identification:
  - [ ] Generate screen fingerprint (perceptual hash of screenshot)
  - [ ] Track unique screens discovered
  - [ ] Build adjacency graph: Screen A → (click element X) → Screen B
- [ ] Implement `SiteMap` class:
  - [ ] `add_screen(fingerprint, screenshot, url, elements)`
  - [ ] `add_transition(from_screen, element, to_screen)`
  - [ ] `get_unvisited_elements(screen)` → elements not yet clicked
  - [ ] `get_unvisited_screens()` → screens with untested elements
  - [ ] `get_coverage_stats()` → % elements tested, screens discovered
- [ ] Persist site map to disk (JSON) for resume after restart

#### 6.3 Brute Force Navigation Engine (30 min)
- [ ] Create `src/core/brute_force_engine.py`
- [ ] Implement `BruteForceEngine` class:
  - [ ] **Exploration strategy:** Breadth-first across screens
  - [ ] For each screen:
    1. Discover all interactive elements
    2. Click each element one at a time
    3. After each click: capture screenshot, check for errors
    4. Record result: `{ element, action, result_type, new_screen?, error? }`
    5. Navigate back to original screen (via browser back or URL)
    6. Move to next element
  - [ ] After all elements tested → move to next unvisited screen
  - [ ] Handle edge cases:
    - [ ] Modal/popup detection and dismissal
    - [ ] Infinite scroll pages
    - [ ] Form submissions (fill with test data before submit)
    - [ ] External link detection (skip, log)

#### 6.4 Continuous Run Loop (20 min)
- [ ] Implement `run_continuous(target_url, refresh_interval_minutes=60)`:
  - [ ] **Run cycle:**
    1. Open fresh browser instance
    2. Navigate to target URL
    3. Run brute force exploration until all screens covered
    4. Generate run report
    5. Close browser
    6. Wait for `refresh_interval` (allows new deployments)
    7. Repeat from step 1
  - [ ] Track run number and cumulative stats
  - [ ] Compare results between runs to detect **regressions**:
    - [ ] Element that worked before now fails → flag as regression
    - [ ] New screen detected → flag as new feature
    - [ ] Screen missing → flag as potential removal
  - [ ] Graceful shutdown via signal handler (SIGINT/SIGTERM)

#### 6.5 Brute Force Issue Logger (15 min)
- [ ] Create `src/diagnostics/brute_force_logger.py`
- [ ] Log every interaction:
  ```python
  @dataclass
  class InteractionLog:
      run_id: str
      screen_fingerprint: str
      element_label: str
      element_type: str
      action: str             # click, type, scroll
      result: str             # navigated, error, no_change, crash
      error_details: Optional[dict]  # Diagnosis if error
      screenshot_before: str
      screenshot_after: str
      timestamp: datetime
      response_time_ms: int   # How long the page took to respond
  ```
- [ ] Aggregate issues per run into summary report
- [ ] Send alerts only for new/unique issues (avoid alert fatigue)

#### 6.6 Dashboard Integration (15 min)
- [ ] Add **"Brute Force"** tab to Streamlit dashboard:
  - [ ] **Controls:**
    - Start/Stop Brute Force Mode button
    - Refresh interval slider (15-120 min)
    - Target URL display
  - [ ] **Live Stats:**
    - Screens discovered: N
    - Elements tested: N / Total
    - Coverage: X%
    - Issues found: N (P0: X, P1: X, P2: X, P3: X)
    - Current run #, uptime
  - [ ] **Site Map Visualization:**
    - Simple node graph of discovered screens
    - Red nodes = screens with issues
    - Green nodes = clean screens
  - [ ] **Issue Feed:**
    - Scrolling log of discovered issues
    - Filter by severity
    - Expandable with screenshots

**Phase 6 Deliverables:**
- ✅ Autonomous element discovery on every screen
- ✅ Systematic click-everything testing
- ✅ Site map with coverage tracking
- ✅ 24/7 continuous run with app refresh between cycles
- ✅ Regression detection across runs
- ✅ Dashboard with coverage stats and site map

---

## 📊 Project Structure

```
Deriv-Hackathon/
├── .env                          # Environment variables (gitignored)
├── .env.example                  # Template for .env
├── .gitignore
├── README.md                     # Project overview & setup
├── implementation-plan.md        # This file
├── TESTING.md                    # Test results log
├── requirements.txt              # Python dependencies
├── src/
│   ├── __init__.py
│   ├── ai/
│   │   ├── __init__.py
│   │   └── vision_navigator.py  # Gemini Flash 2.5 integration
│   ├── browser/
│   │   ├── __init__.py
│   │   ├── playwright_manager.py
│   │   ├── action_executor.py
│   │   └── network_monitor.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── navigation_engine.py  # Objective-driven loop
│   │   ├── brute_force_engine.py # Brute force exploration
│   │   ├── element_discovery.py  # Interactive element detection
│   │   └── site_mapper.py        # Screen graph & coverage
│   ├── diagnostics/
│   │   ├── __init__.py
│   │   ├── failure_detector.py
│   │   ├── issue_analyzer.py
│   │   └── brute_force_logger.py # Interaction logging for BF mode
│   ├── vision/
│   │   ├── __init__.py
│   │   ├── screenshot_handler.py
│   │   └── annotator.py
│   ├── alerting/
│   │   ├── __init__.py
│   │   └── teams_notifier.py
│   ├── personas/
│   │   ├── __init__.py
│   │   └── user_personas.py
│   ├── testcases/
│   │   ├── __init__.py
│   │   ├── test_case_model.py   # TestCase & TestCaseResult dataclasses
│   │   └── test_case_store.py   # JSON persistence layer
│   ├── utils/
│   │   ├── __init__.py
│   │   └── progress_detector.py
│   └── ui/
│       ├── __init__.py
│       └── dashboard.py         # Streamlit app (all tabs)
├── testcases/
│   ├── saved/                   # Saved test case definitions
│   └── results/                 # Run history per test case
├── tests/
│   ├── __init__.py
│   ├── test_vision_navigation.py
│   └── test_signup_flow.py
└── screenshots/                 # Auto-generated screenshots
```

---

## ⏱️ Time Allocation Summary

| Phase | Focus Area | Duration |
|-------|-----------|----------|
| **Phase 1** | Vision-to-Action Foundation | 2.5 hours |
| **Phase 2** | Autonomous Navigation Loop | 2.5 hours |
| **Phase 3** | Diagnosis & Intelligence | 2.5 hours |
| **Phase 4** | UI & Alerting | 2.5 hours |
| **Phase 5** | Prompt-Driven Test Cases | 2 hours |
| **Phase 6** | Brute Force Continuous Testing | 2 hours |
| **Total** | | **14 hours** |

---

## 🎯 Success Criteria

### Minimum Viable Product (MVP)
- [x] Agent navigates mobile signup using only screenshots
- [x] Detects at least one friction point
- [x] Sends Teams alert with severity classification
- [x] Streamlit UI shows live navigation

### Stretch Goals
- [ ] Multi-persona comparison mode
- [ ] Historical session replay
- [ ] A/B test variant detection
- [ ] Automated regression suite

### Prompt-Driven Testing (Phase 5)
- [ ] Users define objectives in natural language
- [ ] Test cases are saved and reusable
- [ ] Run history tracks pass/fail over time
- [ ] Import/export test suites

### Brute Force Mode (Phase 6)
- [ ] Systematic element-by-element exploration
- [ ] Site map with coverage percentage
- [ ] 24/7 continuous operation with auto-refresh
- [ ] Regression detection between runs

---

## 🚀 Getting Started

### Quick Start Commands
```bash
# 1. Setup environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium

# 2. Configure credentials
cp .env.example .env
# Edit .env with your API keys

# 3. Run tests
python -m pytest tests/

# 4. Launch dashboard
streamlit run src/ui/dashboard.py
```

---

## 📝 Notes & Assumptions

1. **Staging URL:** Must support mobile access and not require authentication bypass
2. **Rate Limiting:** Gemini Flash 2.5 has generous rate limits (~1500 RPM on free tier); caching recommended for repeated screens
3. **Concurrency:** Current design is single-threaded; parallel sessions require architecture changes
4. **Data Privacy:** Test data generation must comply with PII regulations
5. **Error Budget:** Expect 10-20% false positives in friction detection during initial runs
6. **Teams Webhooks:** Requires Office 365 Incoming Webhook connector setup in target channel

---

## 🔄 Iteration Strategy

After Phase 4 completion:
1. **Run 10 test sessions** with different personas
2. **Collect metrics:** Success rate, false positives, average navigation time
3. **Refine prompts** based on failure patterns
4. **Tune severity scoring** based on stakeholder feedback
5. **Document edge cases** in TESTING.md

---

**LAST UPDATED:** February 7, 2026  
**STATUS:** Ready for Implementation 🚀
