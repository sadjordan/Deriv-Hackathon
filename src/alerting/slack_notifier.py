"""
Slack Alerting via Block Kit
Sends severity-based notifications with screenshots to Slack channels
"""

import os
import ssl
import certifi
import urllib3
import base64
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from slack_sdk.webhook import WebhookClient

logger = logging.getLogger(__name__)

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Monkey-patch ssl to disable verification globally (for development only)
ssl._create_default_https_context = ssl._create_unverified_context

# Severity mapping
SEVERITY_COLORS = {
    "P0": "danger",  # Red - Critical
    "P1": "warning",  # Yellow - High
    "P2": "#FFD700",  # Gold - Medium
    "P3": "good",  # Green - Low
}

SEVERITY_LABEL = {
    "P0": "CRITICAL",
    "P1": "HIGH",
    "P2": "MEDIUM",
    "P3": "LOW",
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
        else:
            # Create SSL context without verification (to avoid certificate issues)
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            self.webhook_client = WebhookClient(self.webhook_url, ssl=ssl_context)

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
        Send a Block Kit alert to Slack

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
            blocks = self._build_blocks(
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

            color = SEVERITY_COLORS.get(severity, "#808080")
            severity_label = SEVERITY_LABEL.get(severity, severity)
            fallback_text = f"[{severity_label}] {title}: {description}"

            response = self.webhook_client.send(text=fallback_text, blocks=blocks)

            if response.status_code == 200 and response.body == "ok":
                logger.info(f"Slack alert sent: {severity} - {title}")
                return True
            else:
                logger.error(
                    f"Slack webhook failed: {response.status_code} - {response.body}"
                )
                return False

        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")
            return False

    def _build_blocks(
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
    ) -> List[Dict[str, Any]]:
        """Build Block Kit blocks for Slack message"""

        severity_label = SEVERITY_LABEL.get(severity, severity)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": title,
                },
            },
            {"type": "section", "text": {"type": "mrkdwn", "text": description}},
            {"type": "divider"},
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Category:*\n{category}"},
                    {
                        "type": "mrkdwn",
                        "text": f"*Severity:*\n{severity} ({severity_label})",
                    },
                    {"type": "mrkdwn", "text": f"*Step:*\n{step_number}"},
                    {"type": "mrkdwn", "text": f"*Timestamp:*\n{timestamp}"},
                ],
            },
        ]

        # Add URL if provided
        if target_url:
            blocks[-1]["fields"].append(
                {"type": "mrkdwn", "text": f"*URL:*\n<{target_url}|View Page>"}
            )

        # Add suggested fix if provided
        if suggested_fix:
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Suggested Fix:*\n{suggested_fix}",
                    },
                }
            )

        # Add screenshot if available
        screenshot_url_to_use = screenshot_url
        if not screenshot_url_to_use and screenshot_path:
            # Slack doesn't support base64 images directly in Block Kit
            # We need to skip the image block if only local path is available
            # and add a note about it
            logger.warning(
                "Slack Block Kit doesn't support base64 images directly. Use image hosting service for screenshots."
            )

        if screenshot_url_to_use:
            blocks.append(
                {
                    "type": "image",
                    "image_url": screenshot_url_to_use,
                    "alt_text": "Screenshot of issue",
                }
            )

        # Add network logs if provided
        if network_logs:
            log_text = "*Recent Network Activity:*\n```\n"
            for log in network_logs[-3:]:  # Last 3 entries
                status = log.get("status", "?")
                url = log.get("url", "unknown")[:60]
                log_text += f"{status} - {url}\n"
            log_text += "```"

            blocks.append(
                {"type": "section", "text": {"type": "mrkdwn", "text": log_text}}
            )

        # Add action buttons
        actions = []
        if target_url:
            actions.append(
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "View Page",
                    },
                    "url": target_url,
                }
            )

        actions.append(
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "Dashboard"},
                "url": "http://localhost:8501",
            }
        )

        blocks.append({"type": "actions", "elements": actions})

        return blocks

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
