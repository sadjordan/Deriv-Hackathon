"""
Severity Scorer
Assigns priority levels to detected issues
"""

from enum import Enum
from dataclasses import dataclass
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class Severity(Enum):
    """Issue severity levels"""
    P0_CRITICAL = "P0"  # Blocker - prevents flow completion
    P1_HIGH = "P1"      # High - major friction, many users affected
    P2_MEDIUM = "P2"    # Medium - moderate friction, workaround exists
    P3_LOW = "P3"       # Low - minor issue, edge case


@dataclass
class SeverityScore:
    """Severity assessment result"""
    severity: Severity
    confidence: float  # 0-1
    reasoning: str
    impact_description: str
    user_impact_percentage: int  # Estimated % of users affected


class SeverityScorer:
    """Assigns severity levels to issues using rule-based logic"""
    
    def __init__(self):
        logger.info("SeverityScorer initialized")
    
    def score_issue(
        self,
        issue_category: str,
        navigation_state: str,
        step_count: int,
        error_count: int,
        user_stuck: bool,
        description: str
    ) -> SeverityScore:
        """
        Score an issue's severity
        
        Args:
            issue_category: Category of the issue (UX_FRICTION, TECHNICAL_ERROR, etc.)
            navigation_state: Current navigation state (ERROR, STUCK, etc.)
            step_count: Number of steps taken
            error_count: Number of errors encountered
            user_stuck: Whether user is stuck
            description: Issue description
            
        Returns:
            SeverityScore object
        """
        # P0: Critical - Flow blocker
        if navigation_state == "ERROR" or navigation_state == "TIMEOUT":
            if error_count >= 3:
                return SeverityScore(
                    severity=Severity.P0_CRITICAL,
                    confidence=0.95,
                    reasoning="Navigation failed completely - prevents flow completion",
                    impact_description="Users cannot complete the flow",
                    user_impact_percentage=100
                )
        
        # P0: Critical - Stuck with no recovery
        if user_stuck and step_count > 5:
            if any(keyword in description.lower() for keyword in [
                "cannot proceed", "blocked", "broken", "missing button"
            ]):
                return SeverityScore(
                    severity=Severity.P0_CRITICAL,
                    confidence=0.90,
                    reasoning="User stuck with no visible path forward",
                    impact_description="Critical blocker preventing progress",
                    user_impact_percentage=80
                )
        
        # P1: High - Technical errors
        if issue_category == "TECHNICAL_ERROR":
            if any(keyword in description.lower() for keyword in [
                "error message", "crash", "500", "404", "timeout"
            ]):
                return SeverityScore(
                    severity=Severity.P1_HIGH,
                    confidence=0.85,
                    reasoning="Technical error visible to user",
                    impact_description="Users see error messages or broken functionality",
                    user_impact_percentage=60
                )
        
        # P1: High - Major UX friction
        if issue_category == "UX_FRICTION":
            if user_stuck or error_count >= 2:
                return SeverityScore(
                    severity=Severity.P1_HIGH,
                    confidence=0.80,
                    reasoning="Significant friction causing confusion",
                    impact_description="Many users likely to struggle or abandon",
                    user_impact_percentage=50
                )
        
        # P2: Medium - Moderate friction
        if issue_category in ["UX_FRICTION", "ACCESSIBILITY"]:
            if step_count > 10:  # Took many steps
                return SeverityScore(
                    severity=Severity.P2_MEDIUM,
                    confidence=0.75,
                    reasoning="Flow is longer than expected",
                    impact_description="Users experience unnecessary friction",
                    user_impact_percentage=30
                )
        
        # P2: Medium - Confusing UI
        if any(keyword in description.lower() for keyword in [
            "unclear", "confusing", "hard to find", "small text"
        ]):
            return SeverityScore(
                severity=Severity.P2_MEDIUM,
                confidence=0.70,
                reasoning="UI clarity issue detected",
                impact_description="Some users may be confused",
                user_impact_percentage=25
            )
        
        # P3: Low - Minor issues
        return SeverityScore(
            severity=Severity.P3_LOW,
            confidence=0.60,
            reasoning="Minor issue with low impact",
            impact_description="Edge case or cosmetic issue",
            user_impact_percentage=10
        )
    
    def get_severity_details(self, severity: Severity) -> Dict[str, Any]:
        """Get detailed information about a severity level"""
        details = {
            Severity.P0_CRITICAL: {
                "name": "P0 - Critical",
                "color": "red",
                "sla_hours": 2,
                "description": "Blocker preventing flow completion",
                "action_required": "Immediate fix required"
            },
            Severity.P1_HIGH: {
                "name": "P1 - High",
                "color": "orange",
                "sla_hours": 24,
                "description": "Major friction affecting many users",
                "action_required": "Fix in next release"
            },
            Severity.P2_MEDIUM: {
                "name": "P2 - Medium",
                "color": "yellow",
                "sla_hours": 72,
                "description": "Moderate friction with workaround",
                "action_required": "Plan fix for upcoming sprint"
            },
            Severity.P3_LOW: {
                "name": "P3 - Low",
                "color": "blue",
                "sla_hours": 168,
                "description": "Minor issue or edge case",
                "action_required": "Backlog item"
            }
        }
        
        return details.get(severity, {})
