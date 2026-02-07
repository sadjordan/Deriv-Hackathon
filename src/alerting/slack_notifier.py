"""
Slack Alerting via Webhooks
Sends severity-based notifications with screenshots to Slack channels
"""

import os
import json
import base64
import requests
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Severity color mapping for Slack (hex colors)
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


class SlackNotifier:
    """Send alerts to Slack via Incoming Webhook"""

    def __init__(self, webhook_url: Optional[str] = None):
        """
        Initialize Slack notifier

        Args:
            webhook_url: Slack webhook URL (defaults to SLACK_WEBHOOK_URL env var)
        """
        self.webhook_url = webhook_url or os.getenv("SLACK_WEBHOOK_URL")
        if not self.webhook_url:
            logger.warning(
                "SLACK_WEBHOOK_URL not configured - alerts will be logged only"
            )

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
        step_number: int = 0,
    ) -> bool:
        """
        Send a formatted alert to Slack

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
            logger.info(f"[SLACK ALERT] {severity} - {title}: {description}")
            return True

        try:
            payload = self._build_slack_payload(
                title=title,
                description=description,
                severity=severity,
                category=category,
                suggested_fix=suggested_fix,
                screenshot_path=screenshot_path,
                screenshot_url=screenshot_url,
                target_url=target_url,
                network_logs=network_logs,
                step_number=step_number,
            )

            # Send to webhook
            response = requests.post(
                self.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30,
            )

            if response.status_code == 200:
                logger.info(f"Slack alert sent: {severity} - {title}")
                return True
            else:
                logger.error(
                    f"Slack webhook failed: {response.status_code} - {response.text}"
                )
                return False

        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")
            return False

    def _build_slack_payload(self, **kwargs) -> dict:
        """Build Slack message payload with blocks"""

        severity = kwargs.get("severity", "P2")
        color = SEVERITY_COLORS.get(severity, SEVERITY_COLORS["P2"])
        emoji = SEVERITY_EMOJI.get(severity, "🟡")

        title = kwargs.get("title", "Issue Detected")
        description = kwargs.get("description", "")
        category = kwargs.get("category", "Unknown")
        target_url = kwargs.get("target_url", "")
        step_number = kwargs.get("step_number", 0)
        suggested_fix = kwargs.get("suggested_fix", "")

        # Build the main message text
        text = f"{emoji} *{title}*"

        # Build blocks for rich formatting
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{emoji} {title}",
                    "emoji": True,
                },
            },
            {"type": "section", "text": {"type": "mrkdwn", "text": description}},
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Category:*\n{category}"},
                    {"type": "mrkdwn", "text": f"*Severity:*\n{emoji} {severity}"},
                    {"type": "mrkdwn", "text": f"*Step:*\n{step_number}"},
                    {
                        "type": "mrkdwn",
                        "text": f"*Timestamp:*\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                    },
                ],
            },
        ]

        # Add URL if provided
        if target_url:
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*URL:*\n<{target_url}|{target_url[:50]}...>"
                        if len(target_url) > 50
                        else f"*URL:*\n<{target_url}|{target_url}>",
                    },
                }
            )

        # Add suggested fix if provided
        if suggested_fix:
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Suggested Fix:*\n🛠️ {suggested_fix}",
                    },
                }
            )

        # Add divider before actions
        blocks.append({"type": "divider"})

        # Add actions
        actions = {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "View Dashboard",
                        "emoji": True,
                    },
                    "url": "http://localhost:8501",
                    "action_id": "view_dashboard",
                }
            ],
        }

        if target_url:
            actions["elements"].insert(
                0,
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Open URL", "emoji": True},
                    "url": target_url,
                    "action_id": "open_url",
                },
            )

        blocks.append(actions)

        # Build attachment with screenshot if available
        attachments = []
        screenshot_url = kwargs.get("screenshot_url")

        if not screenshot_url and kwargs.get("screenshot_path"):
            # For Slack, we can't embed base64 images directly in blocks
            # We'll add a note about the screenshot in the text
            screenshot_path = kwargs["screenshot_path"]
            blocks.insert(
                1,
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"📸 Screenshot saved: `{screenshot_path}`",
                        }
                    ],
                },
            )
        elif screenshot_url:
            # If we have a public URL, we can show the image
            attachments.append(
                {
                    "color": color,
                    "blocks": [
                        {
                            "type": "image",
                            "image_url": screenshot_url,
                            "alt_text": "Screenshot of issue",
                        }
                    ],
                }
            )

        # Build full payload
        payload = {"text": text, "blocks": blocks}

        if attachments:
            payload["attachments"] = attachments

        return payload

    def send_issue_alert(
        self, issue: Dict[str, Any], screenshot_path: Optional[str] = None
    ) -> bool:
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
            step_number=issue.get("step_number", 0),
        )
