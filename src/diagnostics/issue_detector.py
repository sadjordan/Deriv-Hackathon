"""
Issue Detector
AI-powered issue detection and diagnosis
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime

from src.diagnostics.severity_scorer import SeverityScorer, SeverityScore, Severity
from src.diagnostics.issue_categorizer import IssueCategorizer, CategorizedIssue, IssueCategory
from src.ai.vision_navigator import GeminiVisionNavigator

logger = logging.getLogger(__name__)


@dataclass
class DetectedIssue:
    """A fully diagnosed issue"""
    issue_id: str
    title: str
    description: str
    category: IssueCategory
    subcategory: Optional[str]
    severity: Severity
    severity_score: SeverityScore
    categorization: CategorizedIssue
    step_number: int
    screenshot_path: str
    navigation_state: str
    error_count: int
    root_cause: Optional[str] = None
    recommended_fix: Optional[str] = None
    ai_analysis: Optional[Dict[str, Any]] = None  # Full AI diagnosis dict
    detected_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


class IssueDetector:
    """Detects and diagnoses issues during navigation"""
    
    def __init__(self, google_api_key: Optional[str] = None):
        """
        Initialize issue detector
        
        Args:
            google_api_key: Optional API key for AI-powered root cause analysis
        """
        self.categorizer = IssueCategorizer()
        self.severity_scorer = SeverityScorer()
        self.vision_navigator = GeminiVisionNavigator(google_api_key) if google_api_key else None
        self.issue_counter = 0
        
        logger.info("IssueDetector initialized")
    
    def detect_issue(
        self,
        description: str,
        step_number: int,
        screenshot_path: str,
        navigation_state: str,
        error_count: int,
        action_type: str = "",
        error_message: str = "",
        screenshot_b64: Optional[str] = None
    ) -> DetectedIssue:
        """
        Detect and fully diagnose an issue
        
        Args:
            description: Issue description
            step_number: Current step number
            screenshot_path: Path to screenshot
            navigation_state: Current navigation state
            error_count: Number of errors so far
            action_type: Type of action that failed
            error_message: Any error message
            screenshot_b64: Optional base64 screenshot for AI analysis
            
        Returns:
            DetectedIssue object
        """
        self.issue_counter += 1
        issue_id = f"ISSUE-{self.issue_counter:04d}"
        
        logger.info(f"Detecting issue {issue_id}: {description}")
        
        # 1. Categorize the issue
        categorization = self.categorizer.categorize(
            description=description,
            navigation_state=navigation_state,
            action_type=action_type,
            error_message=error_message
        )
        
        logger.info(f"Category: {categorization.category.value} ({categorization.confidence:.2f})")
        
        # 2. Score severity
        user_stuck = navigation_state == "STUCK"
        severity_score = self.severity_scorer.score_issue(
            issue_category=categorization.category.value,
            navigation_state=navigation_state,
            step_count=step_number,
            error_count=error_count,
            user_stuck=user_stuck,
            description=description
        )
        
        logger.info(f"Severity: {severity_score.severity.value} ({severity_score.confidence:.2f})")
        
        # 3. Generate title
        title = self._generate_title(categorization, severity_score, description)
        
        # 4. AI-powered root cause analysis (if available and high severity)
        root_cause = None
        recommended_fix = None
        ai_analysis: Optional[Dict[str, Any]] = None
        
        if self.vision_navigator and screenshot_b64:
            if severity_score.severity in [Severity.P0_CRITICAL, Severity.P1_HIGH]:
                logger.info("Running AI root cause analysis...")
                ai_analysis = self._ai_root_cause_analysis(
                    screenshot_b64=screenshot_b64,
                    description=description,
                    category=categorization.category.value,
                    navigation_state=navigation_state
                )
                
                # Extract root cause and fix from AI analysis
                root_cause, recommended_fix = self._parse_ai_analysis(ai_analysis)
        
        # 5. Rule-based root cause (if no AI analysis)
        if not root_cause:
            root_cause, recommended_fix = self._rule_based_root_cause(
                categorization.category,
                description,
                navigation_state
            )
        
        # Create detected issue
        issue = DetectedIssue(
            issue_id=issue_id,
            title=title,
            description=description,
            category=categorization.category,
            subcategory=categorization.subcategory,
            severity=severity_score.severity,
            severity_score=severity_score,
            categorization=categorization,
            step_number=step_number,
            screenshot_path=screenshot_path,
            navigation_state=navigation_state,
            error_count=error_count,
            root_cause=root_cause,
            recommended_fix=recommended_fix,
            ai_analysis=ai_analysis,
            metadata={
                "action_type": action_type,
                "error_message": error_message,
                "keywords_matched": categorization.keywords_matched
            }
        )
        
        logger.info(f"Issue detected: {issue.title}")
        logger.info(f"Root cause: {root_cause}")
        
        return issue
    
    def _generate_title(
        self,
        categorization: CategorizedIssue,
        severity_score: SeverityScore,
        description: str
    ) -> str:
        """Generate a concise title for the issue"""
        severity = severity_score.severity.value
        category = categorization.subcategory or categorization.category.value
        
        # Truncate description to first sentence or 60 chars
        desc_short = description.split('.')[0][:60]
        
        return f"[{severity}] {category}: {desc_short}"
    
    def _ai_root_cause_analysis(
        self,
        screenshot_b64: str,
        description: str,
        category: str,
        navigation_state: str
    ) -> Dict[str, Any]:
        """Use Gemini to analyze root cause"""
        try:
            # Use diagnose_failure from vision_navigator
            # Returns dict with: category, description, severity, suggested_fix
            diagnosis = self.vision_navigator.diagnose_failure(
                screenshot_base64=screenshot_b64,
                context=f"{description} (Category: {category}, State: {navigation_state})"
            )
            
            return diagnosis
            
        except Exception as e:
            logger.error(f"AI root cause analysis failed: {str(e)}")
            return {}
    
    def _parse_ai_analysis(self, ai_analysis: Dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
        """Parse root cause and fix from AI analysis dict"""
        if not ai_analysis:
            return None, None
        
        # Extract from vision_navigator's diagnose_failure response
        # Dict keys: category, description, severity, suggested_fix
        root_cause = ai_analysis.get("description", None)
        recommended_fix = ai_analysis.get("suggested_fix", None)
        
        return root_cause, recommended_fix
    
    def _rule_based_root_cause(
        self,
        category: IssueCategory,
        description: str,
        navigation_state: str
    ) -> tuple[str, str]:
        """Generate rule-based root cause and fix recommendations"""
        rules = {
            IssueCategory.UX_FRICTION: (
                "UI elements are unclear or hard to locate",
                "Improve button labels, add visual cues, or simplify layout"
            ),
            IssueCategory.TECHNICAL_ERROR: (
                "System error or broken functionality",
                "Check server logs, fix API endpoint, or handle error gracefully"
            ),
            IssueCategory.ACCESSIBILITY: (
                "Touch targets too small or text hard to read",
                "Increase button size to 44x44px minimum, use larger font sizes"
            ),
            IssueCategory.PERFORMANCE: (
                "Page loading too slowly",
                "Optimize assets, add loading indicators, reduce bundle size"
            ),
            IssueCategory.BROKEN_FLOW: (
                "Missing button or incomplete user flow",
                "Add missing navigation elements or complete the flow"
            ),
            IssueCategory.FORM_VALIDATION: (
                "Input validation requirements unclear",
                "Show validation requirements upfront, provide helpful error messages"
            ),
            IssueCategory.NAVIGATION: (
                "Navigation structure confusing",
                "Simplify navigation, add breadcrumbs, or provide back button"
            ),
            IssueCategory.CONTENT: (
                "Missing or unclear information",
                "Add help text, tooltips, or explanatory content"
            )
        }
        
        root_cause, fix = rules.get(category, ("Unknown root cause", "Manual investigation required"))
        
        # Enhance with navigation state
        if navigation_state == "STUCK":
            root_cause += " - User unable to proceed"
        elif navigation_state == "ERROR":
            root_cause += " - Critical failure occurred"
        
        return root_cause, fix
    
    def generate_report(self, issues: List[DetectedIssue]) -> Dict[str, Any]:
        """
        Generate a summary report of all detected issues
        
        Args:
            issues: List of detected issues
            
        Returns:
            Summary report dictionary
        """
        if not issues:
            return {
                "total_issues": 0,
                "by_severity": {},
                "by_category": {},
                "summary": "No issues detected"
            }
        
        # Count by severity
        by_severity = {}
        for severity in Severity:
            count = sum(1 for issue in issues if issue.severity == severity)
            if count > 0:
                by_severity[severity.value] = count
        
        # Count by category
        by_category = {}
        for category in IssueCategory:
            count = sum(1 for issue in issues if issue.category == category)
            if count > 0:
                by_category[category.value] = count
        
        # Critical issues
        critical_issues = [
            issue for issue in issues
            if issue.severity in [Severity.P0_CRITICAL, Severity.P1_HIGH]
        ]
        
        report = {
            "total_issues": len(issues),
            "by_severity": by_severity,
            "by_category": by_category,
            "critical_count": len(critical_issues),
            "critical_issues": [
                {
                    "id": issue.issue_id,
                    "title": issue.title,
                    "severity": issue.severity.value,
                    "category": issue.category.value,
                    "step": issue.step_number
                }
                for issue in critical_issues
            ],
            "summary": self._generate_summary(issues, by_severity, by_category)
        }
        
        return report
    
    def _generate_summary(
        self,
        issues: List[DetectedIssue],
        by_severity: Dict[str, int],
        by_category: Dict[str, int]
    ) -> str:
        """Generate human-readable summary"""
        total = len(issues)
        p0_count = by_severity.get("P0", 0)
        p1_count = by_severity.get("P1", 0)
        
        if p0_count > 0:
            return f"❌ Critical: {p0_count} P0 blocker(s) detected - immediate action required"
        elif p1_count > 0:
            return f"⚠️  Warning: {p1_count} P1 issue(s) detected - fix recommended"
        elif total > 0:
            return f"ℹ️  Info: {total} minor issue(s) detected"
        else:
            return "✅ No issues detected"
