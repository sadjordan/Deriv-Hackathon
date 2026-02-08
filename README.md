# Autonomous Mystery Shopper 🤖

An AI-powered agent that autonomously navigates mobile applications using **vision-only** navigation, detects UX friction points, categorizes issues by severity, and provides AI-powered root cause analysis.

## 🎯 Project Overview

This system uses Google's Gemini Flash 2.5 Vision AI to analyze screenshots and navigate mobile web applications without relying on CSS selectors or DOM inspection. It automatically detects issues, categorizes them by severity (P0-P3), and provides actionable fix recommendations.

### Key Features

- **Vision-First Navigation**: No selectors - the AI "sees" the screen like a human
- **Mobile Emulation**: iPhone 13 viewport for realistic testing
- **AI-Powered Diagnosis**: Automatic issue detection with severity scoring (P0-P3)
- **Issue Categorization**: 8 issue categories (UX Friction, Technical Error, Accessibility, etc.)
- **Root Cause Analysis**: AI-powered or rule-based root cause identification
- **Actionable Recommendations**: Specific fix suggestions for each detected issue

## 🛠️ Technology Stack

- **Python 3.10+**
- **Playwright** - Browser automation with mobile emulation
- **Google Gemini Flash 2.5** - Vision AI for navigation and diagnosis
- **Pillow** - Image processing and annotations
- **Streamlit** - Basic frontend for displaying the app

## 📦 Installation

### Prerequisites

- Python 3.10 or higher
- Google API key ([Get one here](https://makersuite.google.com/app/apikey))

### Setup

```bash
# 1. Clone the repository
cd Deriv-Hackathon

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Install Playwright browsers
playwright install chromium

# 5. Configure environment
cp .env.example .env
# Edit .env and add your GOOGLE_API_KEY
```

## 🚀 Quick Start

```bash
python streamlit run src/ui/app.py
```

This tests:
- Severity scoring (P0-P3)
- Issue categorization (8 categories)
- Full issue detection
- Report generation

### Run End-to-End Navigation with Issue Detection

```python
from src.core.navigation_engine import NavigationEngine

engine = NavigationEngine(google_api_key="your_key")

session = engine.run_session(
    url="https://staging.example.com/signup",
    objective="Complete the signup flow",
    max_steps=20,
    max_errors=3
)

# Check for issues
print(f"Issues detected: {len(session.issues_detected)}")
for issue in session.issues_detected:
    print(f"[{issue['severity']}] {issue['title']}")

engine.cleanup()
```

## 📁 Project Structure

```
Deriv-Hackathon/
├── src/
│   ├── ai/
│   │   └── vision_navigator.py      # Gemini Vision integration
│   ├── browser/
│   │   ├── playwright_manager.py    # Mobile browser management
│   │   └── action_executor.py       # Coordinate-based actions
│   ├── vision/
│   │   └── screenshot_handler.py    # Screenshot capture & annotation
│   ├── core/
│   │   └── navigation_engine.py     # Autonomous navigation loop
│   ├── diagnostics/                  # Phase 3: Issue detection
│   │   ├── issue_detector.py        # Main detector
│   │   ├── severity_scorer.py       # P0-P3 scoring
│   │   └── issue_categorizer.py     # Issue categorization
│   └── utils/
│       ├── test_data_generator.py   # Form input generation
│       └── progress_detector.py     # Stuck detection
├── tests/
│   ├── test_vision_navigation.py    # Phase 1 POC
│   └── test_diagnostics.py          # Phase 3 tests
├── screenshots/                      # Auto-generated screenshots
└── README.md
```

## 🧪 Usage Examples

### Example 1: Detect and Diagnose an Issue

```python
from src.diagnostics.issue_detector import IssueDetector

detector = IssueDetector(google_api_key="your_key")

issue = detector.detect_issue(
    description="Cannot find the submit button - unclear where to proceed",
    step_number=5,
    screenshot_path="screenshots/step_5.png",
    navigation_state="STUCK",
    error_count=2,
    action_type="click"
)

print(f"Issue: {issue.title}")
print(f"Severity: {issue.severity.value}")
print(f"Category: {issue.category.value}")
print(f"Root Cause: {issue.root_cause}")
print(f"Fix: {issue.recommended_fix}")
```

Output:
```
Issue: [P1] Cannot Progress: Cannot find the submit button
Severity: P1
Category: BROKEN_FLOW
Root Cause: Missing button or incomplete user flow - User unable to proceed
Fix: Add missing navigation elements or complete the flow
```

### Example 2: Generate Issue Report

```python
from src.diagnostics.issue_detector import IssueDetector

detector = IssueDetector()

# After detecting multiple issues...
report = detector.generate_report(issues)

print(report['summary'])
# Output: "❌ Critical: 2 P0 blocker(s) detected - immediate action required"

print(f"Total issues: {report['total_issues']}")
print(f"By severity: {report['by_severity']}")
# Output: {'P0': 2, 'P1': 3, 'P2': 1}
```

## 📊 Issue Severity Levels

| Severity | Description | SLA | Action Required |
|----------|-------------|-----|-----------------|
| **P0 - Critical** | Blocker preventing flow completion | 2 hours | Immediate fix required |
| **P1 - High** | Major friction affecting many users | 24 hours | Fix in next release |
| **P2 - Medium** | Moderate friction with workaround | 72 hours | Plan fix for upcoming sprint |
| **P3 - Low** | Minor issue or edge case | 1 week | Backlog item |

## Troubleshooting

### "GOOGLE_API_KEY not found"
- Ensure `.env` file exists in project root
- Check that `GOOGLE_API_KEY` is set correctly

### Playwright errors
```bash
playwright install chromium --force
```

### Import errors
```bash
pip install -r requirements.txt
```


**Built for the Deriv Hackathon 2026** 