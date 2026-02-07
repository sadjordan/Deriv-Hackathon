"""
Microsoft Teams Alerting via Adaptive Cards
Sends severity-based notifications with screenshots to Teams channels
"""

import os
import json
import base64
import requests
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Severity color mapping
SEVERITY_COLORS = {
    "P0": "#FF0000",  # Red - Critical
    "P1": "#FF8C00",  # Orange - High
    "P2": "#FFD700",  # Yellow - Medium
    "P3": "#32CD32",  # Green - Low
}

SEVERITY_EMOJI = {
    "P0": "🔴",
    "P1": "🟠", 
    "P2": "🟡",
    "P3": "🟢",
}


class TeamsNotifier:
    """Send alerts to Microsoft Teams via Incoming Webhook"""
    
    def __init__(self, webhook_url: Optional[str] = None):
        """
        Initialize Teams notifier
        
        Args:
            webhook_url: Teams webhook URL (defaults to TEAMS_WEBHOOK_URL env var)
        """
        self.webhook_url = webhook_url or os.getenv("TEAMS_WEBHOOK_URL")
        if not self.webhook_url:
            logger.warning("TEAMS_WEBHOOK_URL not configured - alerts will be logged only")
    
    def send_alert(
        self,
        title: str,
        description: str,
        severity: str = "P2",
        category: str = "Unknown",
        suggested_fix: str = "",
        screenshot_path: Optional[str] = None,
        screenshot_url: Optional[str] = None,
        target_url: str = "",
        network_logs: Optional[List[dict]] = None,
        step_number: int = 0
    ) -> bool:
        """
        Send an Adaptive Card alert to Teams
        
        Args:
            title: Issue title
            description: Detailed description
            severity: P0/P1/P2/P3
            category: Issue category (UI_GLITCH, SERVER_ERROR, etc.)
            suggested_fix: Recommended fix
            screenshot_path: Local path to screenshot (will be base64 encoded)
            screenshot_url: Public URL to screenshot (preferred over path)
            target_url: URL where issue occurred
            network_logs: List of relevant network log entries
            step_number: Navigation step where issue occurred
        
        Returns:
            True if alert sent successfully
        """
        if not self.webhook_url:
            logger.info(f"[TEAMS ALERT] {severity} - {title}: {description}")
            return True
        
        try:
            card = self._build_adaptive_card(
                title=title,
                description=description,
                severity=severity,
                category=category,
                suggested_fix=suggested_fix,
                screenshot_path=screenshot_path,
                screenshot_url=screenshot_url,
                target_url=target_url,
                network_logs=network_logs,
                step_number=step_number
            )
            
            # Send to webhook
            response = requests.post(
                self.webhook_url,
                json=card,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            
            if response.status_code == 200:
                logger.info(f"Teams alert sent: {severity} - {title}")
                return True
            else:
                logger.error(f"Teams webhook failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to send Teams alert: {e}")
            return False
    
    def _build_adaptive_card(self, **kwargs) -> dict:
        """Build Adaptive Card JSON payload"""
        
        severity = kwargs.get("severity", "P2")
        color = SEVERITY_COLORS.get(severity, SEVERITY_COLORS["P2"])
        emoji = SEVERITY_EMOJI.get(severity, "🟡")
        
        # Build facts section
        facts = [
            {"title": "Category", "value": kwargs.get("category", "Unknown")},
            {"title": "Severity", "value": f"{emoji} {severity}"},
            {"title": "Step", "value": str(kwargs.get("step_number", 0))},
            {"title": "Timestamp", "value": datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
        ]
        
        if kwargs.get("target_url"):
            facts.append({"title": "URL", "value": kwargs["target_url"]})
        
        # Build body
        body = [
            {
                "type": "TextBlock",
                "size": "Large",
                "weight": "Bolder",
                "text": f"{emoji} {kwargs.get('title', 'Issue Detected')}",
                "wrap": True
            },
            {
                "type": "TextBlock",
                "text": kwargs.get("description", ""),
                "wrap": True
            },
            {
                "type": "FactSet",
                "facts": facts
            }
        ]
        
        # Add screenshot if available
        screenshot_url = kwargs.get("screenshot_url")
        if not screenshot_url and kwargs.get("screenshot_path"):
            # Convert local file to base64
            screenshot_url = self._encode_screenshot(kwargs["screenshot_path"])
        
        if screenshot_url:
            body.append({
                "type": "Image",
                "url": screenshot_url,
                "size": "Large",
                "altText": "Screenshot of issue"
            })
        
        # Add suggested fix if provided
        if kwargs.get("suggested_fix"):
            body.append({
                "type": "TextBlock",
                "text": f"**Suggested Fix:** {kwargs['suggested_fix']}",
                "wrap": True,
                "color": "Good"
            })
        
        # Add network logs if provided
        network_logs = kwargs.get("network_logs")
        if network_logs:
            log_text = "**Recent Network Activity:**\n"
            for log in network_logs[-3:]:  # Last 3 entries
                status = log.get("status", "?")
                url = log.get("url", "unknown")[:50]
                log_text += f"• {status} - {url}\n"
            body.append({
                "type": "TextBlock",
                "text": log_text,
                "wrap": True,
                "fontType": "Monospace",
                "size": "Small"
            })
        
        # Build full card
        card = {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": {
                        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                        "type": "AdaptiveCard",
                        "version": "1.4",
                        "msteams": {
                            "width": "Full"
                        },
                        "body": body,
                        "actions": [
                            {
                                "type": "Action.OpenUrl",
                                "title": "View Dashboard",
                                "url": "http://localhost:8501"  # Streamlit default
                            }
                        ]
                    }
                }
            ]
        }
        
        return card
    
    def _encode_screenshot(self, path: str) -> Optional[str]:
        """Convert screenshot to base64 data URI"""
        try:
            with open(path, "rb") as f:
                data = base64.b64encode(f.read()).decode("utf-8")
            return f"data:image/png;base64,{data}"
        except Exception as e:
            logger.warning(f"Failed to encode screenshot: {e}")
            return None
    
    def send_issue_alert(self, issue: Dict[str, Any], screenshot_path: Optional[str] = None) -> bool:
        """
        Convenience method to send alert from a DetectedIssue dict
        
        Args:
            issue: Dict with keys: title, description, severity, category, suggested_fix, etc.
            screenshot_path: Optional path to screenshot
        
        Returns:
            True if sent successfully
        """
        return self.send_alert(
            title=issue.get("title", "Issue Detected"),
            description=issue.get("description", ""),
            severity=issue.get("severity", "P2"),
            category=issue.get("category", "Unknown"),
            suggested_fix=issue.get("suggested_fix", ""),
            screenshot_path=screenshot_path,
            step_number=issue.get("step_number", 0)
        )
