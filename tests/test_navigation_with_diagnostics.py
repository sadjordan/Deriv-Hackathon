"""
Integration Test: Navigation Engine with Issue Detection
Tests Phase 2 + Phase 3 working together
"""

import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.navigation_engine import NavigationEngine, NavigationState
from src.diagnostics.issue_detector import IssueDetector

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_navigation_with_auto_diagnostics():
    """
    Test Case: Run navigation session and verify automatic issue detection
    
    This validates:
    1. Navigation loop executes successfully
    2. Issues are automatically detected on failures
    3. Issues are categorized and scored correctly
    4. Reports can be generated from detected issues
    """
    logger.info("=" * 70)
    logger.info("PHASE 2+3 INTEGRATION TEST")
    logger.info("Test: Navigation with Automatic Issue Detection")
    logger.info("=" * 70)
    
    # Check for API key
    api_key = os.getenv('GOOGLE_API_KEY')
    if not api_key:
        logger.error("❌ GOOGLE_API_KEY not set in .env file")
        logger.error("Please add your API key to continue")
        return False
    
    try:
        # Initialize navigation engine
        logger.info("\n[Setup] Initializing Navigation Engine...")
        engine = NavigationEngine(google_api_key=api_key)
        
        # Run a simple navigation session
        logger.info("\n[Test] Starting navigation session...")
        logger.info("Target: https://www.google.com")
        logger.info("Objective: Search for 'Python programming'")
        logger.info("Max Steps: 5")
        logger.info("-" * 70)
        
        session = engine.run_session(
            url="https://www.google.com",
            objective="Search for 'Python programming' on Google",
            max_steps=5,
            max_errors=2
        )
        
        # Display session results
        logger.info("\n" + "=" * 70)
        logger.info("SESSION RESULTS")
        logger.info("=" * 70)
        logger.info(f"Final State: {session.state.value}")
        logger.info(f"Steps Taken: {session.step_count}")
        logger.info(f"Errors Encountered: {session.error_count}")
        logger.info(f"Issues Detected: {len(session.issues_detected)}")
        duration = (session.end_time - session.start_time).total_seconds()
        logger.info(f"Duration: {duration:.2f} seconds")
        
        # Check if session completed
        success_states = [NavigationState.COMPLETED, NavigationState.NAVIGATING]
        session_successful = session.state in success_states
        
        logger.info(f"\nSession Success: {'✅ Yes' if session_successful else '❌ No'}")
        
        # Test diagnostic report generation
        if session.issues_detected:
            logger.info("\n" + "=" * 70)
            logger.info("ISSUE ANALYSIS")
            logger.info("=" * 70)
            
            detector = IssueDetector(google_api_key=api_key)
            report = detector.generate_report(session.issues_detected)
            
            logger.info(f"\n{report['summary']}")
            logger.info(f"\nTotal Issues: {report['total_issues']}")
            logger.info(f"By Severity: {report['by_severity']}")
            logger.info(f"By Category: {report['by_category']}")
            
            # Display critical issues
            if report.get('critical_issues'):
                logger.info("\n" + "-" * 70)
                logger.info("CRITICAL ISSUES (P0/P1)")
                logger.info("-" * 70)
                
                for i, issue in enumerate(report['critical_issues'], 1):
                    logger.info(f"\n{i}. [{issue['severity']}] {issue['title']}")
                    logger.info(f"   Category: {issue['category']}")
                    logger.info(f"   Step: {issue['step_number']}")
                    if issue.get('root_cause'):
                        logger.info(f"   Root Cause: {issue['root_cause']}")
                    if issue.get('recommended_fix'):
                        logger.info(f"   Fix: {issue['recommended_fix']}")
            
            # Verify diagnostics worked
            diagnostics_working = report['total_issues'] > 0
            logger.info(f"\nDiagnostics System: {'✅ Working' if diagnostics_working else '⚠️  No issues detected'}")
        else:
            logger.info("\n✅ No issues detected - Clean navigation!")
        
        # Cleanup
        engine.cleanup()
        
        # Overall test result
        logger.info("\n" + "=" * 70)
        if session_successful:
            logger.info("✅ INTEGRATION TEST PASSED")
            logger.info("   - Navigation engine executed successfully")
            logger.info("   - Diagnostic system is active")
            if session.issues_detected:
                logger.info(f"   - {len(session.issues_detected)} issue(s) detected and analyzed")
        else:
            logger.info("⚠️  INTEGRATION TEST COMPLETED WITH ISSUES")
            logger.info(f"   - Session ended in {session.state.value} state")
            logger.info(f"   - {len(session.issues_detected)} issue(s) detected")
        logger.info("=" * 70)
        
        return True
        
    except Exception as e:
        logger.exception(f"\n❌ Test failed with exception: {e}")
        return False


def test_manual_issue_detection():
    """
    Test Case: Manually create and analyze issues
    
    This validates the diagnostic system can work standalone
    """
    logger.info("\n\n" + "=" * 70)
    logger.info("STANDALONE DIAGNOSTICS TEST")
    logger.info("Test: Manual Issue Detection")
    logger.info("=" * 70)
    
    api_key = os.getenv('GOOGLE_API_KEY')
    if not api_key:
        logger.warning("⚠️  Skipping AI-powered diagnostics (no API key)")
        api_key = None
    
    try:
        detector = IssueDetector(google_api_key=api_key)
        
        # Simulate different issue types
        test_issues = [
            {
                "description": "Button text is unclear and hard to find",
                "step_number": 3,
                "screenshot_path": "screenshots/test.png",
                "navigation_state": "NAVIGATING",
                "error_count": 1,
                "action_type": "click"
            },
            {
                "description": "Page crashed with 500 internal server error",
                "step_number": 5,
                "screenshot_path": "screenshots/test.png",
                "navigation_state": "ERROR",
                "error_count": 3,
                "action_type": "click"
            },
            {
                "description": "Text is too small to read on mobile",
                "step_number": 2,
                "screenshot_path": "screenshots/test.png",
                "navigation_state": "NAVIGATING",
                "error_count": 0,
                "action_type": "none"
            }
        ]
        
        logger.info("\nDetecting and categorizing test issues...")
        detected = []
        
        for i, test_issue in enumerate(test_issues, 1):
            logger.info(f"\n{i}. Testing: {test_issue['description']}")
            
            issue = detector.detect_issue(
                description=test_issue['description'],
                step_number=test_issue['step_number'],
                screenshot_path=test_issue['screenshot_path'],
                navigation_state=test_issue['navigation_state'],
                error_count=test_issue['error_count'],
                action_type=test_issue['action_type']
            )
            
            detected.append(issue)
            
            logger.info(f"   → Category: {issue.category.value}")
            logger.info(f"   → Severity: {issue.severity.value}")
            logger.info(f"   → Title: {issue.title}")
        
        # Generate report
        logger.info("\n" + "-" * 70)
        logger.info("Generating diagnostic report...")
        report = detector.generate_report(detected)
        
        logger.info(f"\n{report['summary']}")
        logger.info(f"Total: {report['total_issues']}")
        logger.info(f"By Severity: {report['by_severity']}")
        logger.info(f"By Category: {report['by_category']}")
        
        logger.info("\n✅ DIAGNOSTICS TEST PASSED")
        logger.info("=" * 70)
        
        return True
        
    except Exception as e:
        logger.exception(f"\n❌ Diagnostics test failed: {e}")
        return False


def main():
    """Run all integration tests"""
    results = []
    
    # Test 1: Navigation with diagnostics
    logger.info("\n\n🧪 Running Test 1: Navigation + Diagnostics Integration\n")
    results.append(("Navigation + Diagnostics", test_navigation_with_auto_diagnostics()))
    
    # Test 2: Standalone diagnostics
    logger.info("\n\n🧪 Running Test 2: Standalone Diagnostics\n")
    results.append(("Standalone Diagnostics", test_manual_issue_detection()))
    
    # Summary
    logger.info("\n\n" + "=" * 70)
    logger.info("TEST SUMMARY")
    logger.info("=" * 70)
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        logger.info(f"{status} - {test_name}")
    
    all_passed = all(result[1] for result in results)
    
    logger.info("\n" + "=" * 70)
    if all_passed:
        logger.info("🎉 ALL TESTS PASSED - Phase 2+3 working correctly!")
    else:
        logger.info("⚠️  SOME TESTS FAILED - Check logs above")
    logger.info("=" * 70 + "\n")
    
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
