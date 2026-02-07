"""
Issue Categorizer
Classifies detected issues into categories
"""

from enum import Enum
from dataclasses import dataclass
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


class IssueCategory(Enum):
    """Types of issues that can be detected"""
    UX_FRICTION = "UX_FRICTION"              # Confusing UI, unclear labels
    TECHNICAL_ERROR = "TECHNICAL_ERROR"       # Crashes, 404s, timeouts
    ACCESSIBILITY = "ACCESSIBILITY"           # Small text, poor contrast
    PERFORMANCE = "PERFORMANCE"               # Slow loading, lag
    BROKEN_FLOW = "BROKEN_FLOW"              # Missing steps, dead ends
    FORM_VALIDATION = "FORM_VALIDATION"       # Input errors, unclear requirements
    NAVIGATION = "NAVIGATION"                 # Hard to find buttons, complex flows
    CONTENT = "CONTENT"                       # Missing info, unclear copy


@dataclass
class CategorizedIssue:
    """An issue with its category and details"""
    category: IssueCategory
    subcategory: Optional[str]
    confidence: float
    reasoning: str
    keywords_matched: List[str]


class IssueCategorizer:
    """Categorizes issues based on patterns and keywords"""
    
    def __init__(self):
        """Initialize categorizer with keyword patterns"""
        self.patterns = {
            IssueCategory.UX_FRICTION: {
                "keywords": [
                    "confusing", "unclear", "hard to find", "not obvious",
                    "where is", "can't see", "hidden", "difficult"
                ],
                "subcategories": ["Unclear UI", "Hidden Elements", "Confusing Labels"]
            },
            IssueCategory.TECHNICAL_ERROR: {
                "keywords": [
                    "error", "crash", "500", "404", "timeout", "failed",
                    "broken", "not working", "exception"
                ],
                "subcategories": ["HTTP Error", "JavaScript Error", "Network Timeout"]
            },
            IssueCategory.ACCESSIBILITY: {
                "keywords": [
                    "small text", "hard to read", "low contrast", "tiny button",
                    "can't tap", "too small"
                ],
                "subcategories": ["Small Text", "Touch Target Too Small", "Poor Contrast"]
            },
            IssueCategory.PERFORMANCE: {
                "keywords": [
                    "slow", "loading", "lag", "frozen", "waiting",
                    "spinner", "taking too long"
                ],
                "subcategories": ["Slow Load", "No Loading Indicator", "Page Lag"]
            },
            IssueCategory.BROKEN_FLOW: {
                "keywords": [
                    "stuck", "cannot proceed", "blocked", "dead end",
                    "missing step", "no next button"
                ],
                "subcategories": ["Missing Button", "Dead End", "Incomplete Flow"]
            },
            IssueCategory.FORM_VALIDATION: {
                "keywords": [
                    "invalid input", "validation", "required field",
                    "format", "password requirements", "email error"
                ],
                "subcategories": ["Unclear Requirements", "Validation Error", "Input Format"]
            },
            IssueCategory.NAVIGATION: {
                "keywords": [
                    "can't navigate", "back button", "navigation",
                    "menu", "lost", "where am i"
                ],
                "subcategories": ["Confusing Navigation", "Missing Back Button", "Deep Navigation"]
            },
            IssueCategory.CONTENT: {
                "keywords": [
                    "missing information", "no help", "unclear instructions",
                    "what does this mean", "explanation"
                ],
                "subcategories": ["Missing Help Text", "Unclear Instructions", "No Explanation"]
            }
        }
        
        logger.info("IssueCategorizer initialized")
    
    def categorize(
        self,
        description: str,
        navigation_state: str = "",
        action_type: str = "",
        error_message: str = ""
    ) -> CategorizedIssue:
        """
        Categorize an issue based on description and context
        
        Args:
            description: Issue description from AI or user
            navigation_state: Current navigation state
            action_type: Type of action that failed
            error_message: Any error message captured
            
        Returns:
            CategorizedIssue object
        """
        combined_text = f"{description} {navigation_state} {error_message}".lower()
        
        # Score each category
        scores = {}
        matched_keywords = {}
        
        for category, pattern in self.patterns.items():
            keyword_matches = [
                kw for kw in pattern["keywords"]
                if kw in combined_text
            ]
            
            if keyword_matches:
                scores[category] = len(keyword_matches)
                matched_keywords[category] = keyword_matches
        
        # Priority-based classification
        
        # Technical errors take precedence
        if navigation_state in ["ERROR", "TIMEOUT"]:
            return CategorizedIssue(
                category=IssueCategory.TECHNICAL_ERROR,
                subcategory="System Error",
                confidence=0.90,
                reasoning="Navigation ended in error state",
                keywords_matched=matched_keywords.get(IssueCategory.TECHNICAL_ERROR, [])
            )
        
        # Broken flow if stuck
        if navigation_state == "STUCK":
            return CategorizedIssue(
                category=IssueCategory.BROKEN_FLOW,
                subcategory="Cannot Progress",
                confidence=0.85,
                reasoning="User unable to proceed with flow",
                keywords_matched=matched_keywords.get(IssueCategory.BROKEN_FLOW, [])
            )
        
        # Use keyword scoring
        if scores:
            best_category = max(scores, key=scores.get)
            confidence = min(0.6 + (scores[best_category] * 0.1), 0.95)
            
            # Determine subcategory
            subcategory = self._determine_subcategory(
                best_category,
                matched_keywords[best_category]
            )
            
            return CategorizedIssue(
                category=best_category,
                subcategory=subcategory,
                confidence=confidence,
                reasoning=f"Matched {scores[best_category]} keywords: {matched_keywords[best_category][:3]}",
                keywords_matched=matched_keywords[best_category]
            )
        
        # Default: UX friction
        return CategorizedIssue(
            category=IssueCategory.UX_FRICTION,
            subcategory="General Friction",
            confidence=0.50,
            reasoning="No specific patterns matched, defaulting to UX friction",
            keywords_matched=[]
        )
    
    def _determine_subcategory(
        self,
        category: IssueCategory,
        keywords: List[str]
    ) -> str:
        """Determine subcategory based on matched keywords"""
        subcats = self.patterns[category]["subcategories"]
        
        # Simple heuristic: return first subcategory
        # Could be enhanced with more sophisticated matching
        if subcats:
            return subcats[0]
        
        return "General"
    
    def get_category_description(self, category: IssueCategory) -> str:
        """Get human-readable description of category"""
        descriptions = {
            IssueCategory.UX_FRICTION: "User experience friction - confusing or unclear interface",
            IssueCategory.TECHNICAL_ERROR: "Technical error - crashes, HTTP errors, timeouts",
            IssueCategory.ACCESSIBILITY: "Accessibility issue - text size, touch targets, contrast",
            IssueCategory.PERFORMANCE: "Performance problem - slow loading or lag",
            IssueCategory.BROKEN_FLOW: "Broken user flow - missing steps or dead ends",
            IssueCategory.FORM_VALIDATION: "Form validation issue - unclear input requirements",
            IssueCategory.NAVIGATION: "Navigation problem - hard to find or use navigation",
            IssueCategory.CONTENT: "Content issue - missing information or unclear copy"
        }
        
        return descriptions.get(category, "Unknown category")
