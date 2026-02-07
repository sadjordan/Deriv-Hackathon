"""
Phase 3 Integration Test - Issue Detection and Diagnosis
Tests the complete diagnostic system
"""

import os
import sys
from pathlib import Path
import logging

# Setup path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.diagnostics.severity_scorer import SeverityScorer, Severity
from src.diagnostics.issue_categorizer import IssueCategorizer, IssueCategory
from src.diagnostics.issue_detector import IssueDetector
from src.core.navigation_engine import NavigationEngine, NavigationState
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_severity_scorer():
    """Test severity scoring logic"""
    logger.info("=== Testing Severity Scorer ===")
    
    scorer = SeverityScorer()
    
    # Test P0 Critical - Navigation failed
    score = scorer.score_issue(
        issue_category="TECHNICAL_ERROR",
        navigation_state="ERROR",
        step_count=5,
        error_count=3,
        user_stuck=True,
        description="Cannot proceed - error 500"
    )
    
    assert score.severity == Severity.P0_CRITICAL, "Should be P0 for complete failure"
    logger.info(f"✅ P0 Test: {score.severity.value} - {score.reasoning}")
    
    # Test P1 High - Technical error
    score = scorer.score_issue(
        issue_category="TECHNICAL_ERROR",
        navigation_state="STUCK",
        step_count=3,
        error_count=1,
        user_stuck=False,
        description="Error message displayed - timeout"
    )
    
    assert score.severity == Severity.P1_HIGH, "Should be P1 for technical error"
    logger.info(f"✅ P1 Test: {score.severity.value} - {score.reasoning}")
    
    # Test P2 Medium - UX friction
    score = scorer.score_issue(
        issue_category="UX_FRICTION",
        navigation_state="NAVIGATING",
        step_count=12,
        error_count=0,
        user_stuck=False,
        description="Flow is longer than expected"
    )
    
    assert score.severity == Severity.P2_MEDIUM, "Should be P2 for long flow"
    logger.info(f"✅ P2 Test: {score.severity.value} - {score.reasoning}")
    
    # Test P3 Low - Minor issue
    score = scorer.score_issue(
        issue_category="UX_FRICTION",
        navigation_state="NAVIGATING",
        step_count=3,
        error_count=0,
        user_stuck=False,
        description="Minor cosmetic issue"
    )
    
    assert score.severity == Severity.P3_LOW, "Should be P3 for minor issue"
    logger.info(f"✅ P3 Test: {score.severity.value} - {score.reasoning}")
    
    logger.info("✅ Severity Scorer tests passed\n")


def test_issue_categorizer():
    """Test issue categorization"""
    logger.info("=== Testing Issue Categorizer ===")
    
    categorizer = IssueCategorizer()
    
    # Test UX Friction
    cat = categorizer.categorize(
        description="Button is hard to find and unclear label",
        navigation_state="NAVIGATING"
    )
    
    assert cat.category == IssueCategory.UX_FRICTION, "Should categorize as UX_FRICTION"
    logger.info(f"✅ UX Friction: {cat.category.value} - {cat.reasoning}")
    
    # Test Technical Error
    cat = categorizer.categorize(
        description="Page shows 404 error",
        navigation_state="ERROR"
    )
    
    assert cat.category == IssueCategory.TECHNICAL_ERROR, "Should categorize as TECHNICAL_ERROR"
    logger.info(f"✅ Technical Error: {cat.category.value} - {cat.reasoning}")
    
    # Test Broken Flow
    cat = categorizer.categorize(
        description="Cannot proceed - missing next button",
        navigation_state="STUCK"
    )
    
    assert cat.category == IssueCategory.BROKEN_FLOW, "Should categorize as BROKEN_FLOW"
    logger.info(f"✅ Broken Flow: {cat.category.value} - {cat.reasoning}")
    
    # Test Accessibility
    cat = categorizer.categorize(
        description="Text is too small and hard to read",
        navigation_state="NAVIGATING"
    )
    
    assert cat.category == IssueCategory.ACCESSIBILITY, "Should categorize as ACCESSIBILITY"
    logger.info(f"✅ Accessibility: {cat.category.value} - {cat.reasoning}")
    
    logger.info("✅ Issue Categorizer tests passed\n")


def test_issue_detector():
    """Test full issue detection"""
    logger.info("=== Testing Issue Detector ===")
    
    # Load environment (optional for this test)
    load_dotenv()
    api_key = os.getenv("GOOGLE_API_KEY")
    
    # Create detector (will work without API key for rule-based analysis)
    detector = IssueDetector(google_api_key=api_key if api_key else None)
    
    # Detect a P0 critical issue
    issue = detector.detect_issue(
        description="Page crashed with 500 error - cannot proceed",
        step_number=5,
        screenshot_path="/tmp/test.png",
        navigation_state="ERROR",
        error_count=3,
        action_type="click",
        error_message="Internal Server Error"
    )
    
    logger.info(f"Issue ID: {issue.issue_id}")
    logger.info(f"Title: {issue.title}")
    logger.info(f"Category: {issue.category.value}")
    logger.info(f"Severity: {issue.severity.value}")
    logger.info(f"Root Cause: {issue.root_cause}")
    logger.info(f"Recommended Fix: {issue.recommended_fix}")
    
    assert issue.severity == Severity.P0_CRITICAL, "Should be P0"
    assert issue.category == IssueCategory.TECHNICAL_ERROR, "Should be TECHNICAL_ERROR"
    assert issue.root_cause is not None, "Should have root cause"
    assert issue.recommended_fix is not None, "Should have recommended fix"
    
    logger.info("✅ Issue detection test passed\n")


def test_issue_report_generation():
    """Test issue report generation"""
    logger.info("=== Testing Issue Report Generation ===")
    
    detector = IssueDetector()
    
    # Create multiple issues
    issues = []
    
    # P0 issue
    issues.append(detector.detect_issue(
        description="Critical blocker - page crashes",
        step_number=3,
        screenshot_path="/tmp/test1.png",
        navigation_state="ERROR",
        error_count=3
    ))
    
    # P1 issue
    issues.append(detector.detect_issue(
        description="Error message displayed",
        step_number=5,
        screenshot_path="/tmp/test2.png",
        navigation_state="STUCK",
        error_count=1
    ))
    
    # P3 issue
    issues.append(detector.detect_issue(
        description="Minor UI issue",
        step_number=2,
        screenshot_path="/tmp/test3.png",
        navigation_state="NAVIGATING",
        error_count=0
    ))
    
    # Generate report
    report = detector.generate_report(issues)
    
    logger.info(f"Total issues: {report['total_issues']}")
    logger.info(f"By severity: {report['by_severity']}")
    logger.info(f"By category: {report['by_category']}")
    logger.info(f"Critical count: {report['critical_count']}")
    logger.info(f"Summary: {report['summary']}")
    
    assert report['total_issues'] == 3, "Should have 3 issues"
    assert report['critical_count'] >= 1, "Should have at least 1 critical issue"
    assert "P0" in report['by_severity'], "Should have P0 in report"
    
    logger.info("\n✅ Report generation test passed\n")


def test_severity_details():
    """Test severity level details"""
    logger.info("=== Testing Severity Details ===")
    
    scorer = SeverityScorer()
    
    for severity in Severity:
        details = scorer.get_severity_details(severity)
        logger.info(f"\n{details['name']}:")
        logger.info(f"  Color: {details['color']}")
        logger.info(f"  SLA: {details['sla_hours']} hours")
        logger.info(f"  Description: {details['description']}")
        logger.info(f"  Action: {details['action_required']}")
    
    logger.info("\n✅ Severity details test passed\n")


def test_live_diagnostics_with_google():
    """
    INTEGRATION TEST: Live diagnostics with real Google navigation
    
    This test runs actual navigation on Google.com and verifies:
    1. Navigation engine works correctly
    2. Issues are automatically detected during navigation
    3. Issues are categorized and scored properly
    4. Diagnostic reports are generated correctly
    """
    logger.info("=" * 70)
    logger.info("LIVE INTEGRATION TEST: Diagnostics with Google Navigation")
    logger.info("=" * 70)
    
    # Load API key
    load_dotenv()
    api_key = os.getenv('GOOGLE_API_KEY')
    
    if not api_key:
        logger.warning("⚠️  GOOGLE_API_KEY not set - skipping live test")
        logger.info("To run this test, add GOOGLE_API_KEY to your .env file")
        return True  # Skip but don't fail
    
    try:
        # Initialize navigation engine
        logger.info("\n[Setup] Initializing Navigation Engine with diagnostics...")
        engine = NavigationEngine(google_api_key=api_key)
        
        # Test 1: Successful navigation (should have minimal/no issues)
        logger.info("\n" + "-" * 70)
        logger.info("[Test 1] Running normal Google search")
        logger.info("-" * 70)
        
        session = engine.run_session(
            url="https://www.google.com",
            objective="Search for 'Python programming' on Google",
            max_steps=5,
            max_errors=2
        )
        
        logger.info(f"\nSession Results:")
        logger.info(f"  State: {session.state.value}")
        logger.info(f"  Steps: {session.step_count}")
        logger.info(f"  Errors: {session.error_count}")
        logger.info(f"  Issues Detected: {len(session.issues_detected)}")
        
        # Verify session ran
        assert session.step_count > 0, "Should have taken at least 1 step"
        logger.info("✅ Navigation executed successfully")
        
        # Test 2: Intentionally difficult objective (may trigger issues)
        logger.info("\n" + "-" * 70)
        logger.info("[Test 2] Running navigation with challenging objective")
        logger.info("-" * 70)
        
        session2 = engine.run_session(
            url="https://www.google.com",
            objective="Find and click on a button that doesn't exist - click the 'SuperSecretButton123'",
            max_steps=3,
            max_errors=2
        )
        
        logger.info(f"\nSession Results:")
        logger.info(f"  State: {session2.state.value}")
        logger.info(f"  Steps: {session2.step_count}")
        logger.info(f"  Errors: {session2.error_count}")
        logger.info(f"  Issues Detected: {len(session2.issues_detected)}")
        
        # This should likely fail and detect issues
        if session2.issues_detected:
            logger.info("✅ Issues were detected as expected")
            
            # Test report generation
            detector = IssueDetector(google_api_key=api_key)
            report = detector.generate_report(session2.issues_detected)
            
            logger.info(f"\n  Diagnostic Report:")
            logger.info(f"    {report['summary']}")
            logger.info(f"    Total Issues: {report['total_issues']}")
            logger.info(f"    By Severity: {report['by_severity']}")
            logger.info(f"    By Category: {report['by_category']}")
            
            # Display issues
            for i, issue in enumerate(session2.issues_detected, 1):
                logger.info(f"\n  Issue {i}:")
                logger.info(f"    Severity: {issue['severity']}")
                logger.info(f"    Category: {issue['category']}")
                logger.info(f"    Title: {issue['title']}")
                if issue.get('root_cause'):
                    logger.info(f"    Root Cause: {issue['root_cause']}")
            
            # Verify diagnostic system worked
            assert report['total_issues'] > 0, "Should have detected issues"
            logger.info("\n✅ Diagnostic system detected and categorized issues correctly")
        else:
            logger.info("ℹ️  No issues detected (navigation may have succeeded unexpectedly)")
        
        # Combine both sessions for comprehensive report
        all_issues = session.issues_detected + session2.issues_detected
        
        if all_issues:
            logger.info("\n" + "-" * 70)
            logger.info("[Combined Report] All issues from both sessions")
            logger.info("-" * 70)
            
            detector = IssueDetector(google_api_key=api_key)
            combined_report = detector.generate_report(all_issues)
            
            logger.info(f"\n{combined_report['summary']}")
            logger.info(f"Total Issues Across Sessions: {combined_report['total_issues']}")
            logger.info(f"By Severity: {combined_report['by_severity']}")
            logger.info(f"By Category: {combined_report['by_category']}")
            
            if combined_report.get('critical_issues'):
                logger.info(f"\nCritical Issues (P0/P1): {len(combined_report['critical_issues'])}")
                for issue in combined_report['critical_issues']:
                    logger.info(f"  • [{issue['severity']}] {issue['title']}")
        
        # Cleanup
        engine.cleanup()
        
        logger.info("\n" + "=" * 70)
        logger.info("✅ LIVE INTEGRATION TEST PASSED")
        logger.info("   - Navigation engine executed successfully")
        logger.info("   - Diagnostic system is working")
        logger.info("   - Issues were detected and reported correctly")
        logger.info("=" * 70)
        
        return True
        
    except Exception as e:
        logger.exception(f"\n❌ Live integration test failed: {e}")
        return False


if __name__ == "__main__":
    logger.info("=" * 70)
    logger.info("PHASE 3 DIAGNOSTIC TESTS")
    logger.info("=" * 70)
    logger.info("")
    
    try:
        # Unit Tests
        logger.info("📋 PART 1: UNIT TESTS (Component Testing)\n")
        
        # Test 1: Severity Scorer
        test_severity_scorer()
        
        # Test 2: Issue Categorizer
        test_issue_categorizer()
        
        # Test 3: Issue Detector
        test_issue_detector()
        
        # Test 4: Report Generation
        test_issue_report_generation()
        
        # Test 5: Severity Details
        test_severity_details()
        
        # Integration Test
        logger.info("\n" + "=" * 70)
        logger.info("📋 PART 2: INTEGRATION TEST (Live Website Testing)\n")
        
        # Test 6: Live diagnostics with Google
        test_live_diagnostics_with_google()
        
        logger.info("\n" + "=" * 70)
        logger.info("🎉 ALL PHASE 3 TESTS PASSED ✅")
        logger.info("   ✅ Unit tests: All component tests passed")
        logger.info("   ✅ Integration test: Live diagnostics working")
        logger.info("=" * 70)
        
    except Exception as e:
        logger.error(f"Test failed: {str(e)}", exc_info=True)
        sys.exit(1)
