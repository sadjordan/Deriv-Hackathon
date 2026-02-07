"""
Gemini Vision Navigator
Handles AI-powered visual navigation using Google's Gemini Flash 2.5
"""

import os
import json
import base64
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

# Try new package first, fall back to old if needed
try:
    import google.genai as genai
    GENAI_NEW_API = True
except ImportError:
    import google.generativeai as genai
    GENAI_NEW_API = False

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


@dataclass
class NavigationAction:
    """Represents a navigation action from the AI"""
    action_type: str  # 'click', 'type', 'scroll', 'wait', 'done', 'stuck'
    bounding_box: Optional[List[int]] = None  # [ymin, xmin, ymax, xmax] in 0-1000 scale
    text_to_type: Optional[str] = None
    reasoning: str = ""
    confidence: float = 0.0


class GeminiVisionNavigator:
    """AI-powered navigation using Gemini Vision"""
    
    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-2.5-flash"):
        """
        Initialize Gemini Vision Navigator
        
        Args:
            api_key: Google API key (defaults to GOOGLE_API_KEY env var)
            model_name: Gemini model to use
        """
        self.api_key = api_key or os.getenv('GOOGLE_API_KEY')
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY not found in environment variables")
        
        self.model_name = model_name
        
        # Initialize based on which package is available
        if GENAI_NEW_API:
            # New google.genai package uses Client
            self.client = genai.Client(api_key=self.api_key)
            self.model = None  # Not used in new API
        else:
            # Old google.generativeai package
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(
                model_name=model_name,
                generation_config={
                    "temperature": 0.2,
                    "top_p": 0.95,
                    "top_k": 40,
                    "max_output_tokens": 1024,
                }
            )
            self.client = None
        
        logger.info(f"Gemini Vision Navigator initialized with model: {model_name}")
    
    def get_next_action(
        self,
        screenshot_base64: str,
        objective: str,
        persona: str = "normal_user"
    ) -> NavigationAction:
        """
        Analyze screenshot and determine next action
        
        Args:
            screenshot_base64: Base64 encoded screenshot
            objective: What the agent should accomplish
            persona: User persona for context
            
        Returns:
            NavigationAction object
        """
        # Build prompt
        prompt = self._build_navigation_prompt(objective, persona)
        
        try:
            # Call Gemini API with retry logic
            for attempt in range(3):
                try:
                    if GENAI_NEW_API:
                        response = self.client.models.generate_content(
                            model=self.model_name,
                            contents=[
                                {
                                    "role": "user",
                                    "parts": [
                                        {"text": prompt},
                                        {
                                            "inline_data": {
                                                "mime_type": "image/png",
                                                "data": screenshot_base64
                                            }
                                        }
                                    ]
                                }
                            ]
                        )
                        response_text = response.text
                    else:
                        # Old API structure
                        image_data = {
                            'mime_type': 'image/png',
                            'data': screenshot_base64
                        }
                        response = self.model.generate_content(
                            [prompt, image_data],
                            request_options={"timeout": 30}
                        )
                        response_text = response.text
                    
                    # Parse response
                    action = self._parse_response(response_text)
                    logger.info(f"Action determined: {action.action_type} - {action.reasoning}")
                    
                    return action
                    
                except Exception as e:
                    if attempt == 2:
                        raise
                    logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying...")
                    
        except Exception as e:
            logger.error(f"Failed to get action from Gemini: {e}")
            return NavigationAction(
                action_type="stuck",
                reasoning=f"API Error: {str(e)}"
            )
    
    def diagnose_failure(
        self,
        screenshot_base64: str,
        context: str,
        network_logs: Optional[List[dict]] = None
    ) -> Dict[str, Any]:
        """
        Diagnose what went wrong in a failure scenario
        
        Args:
            screenshot_base64: Screenshot of failure state
            context: Description of what was being attempted
            network_logs: Optional list of recent network requests
            
        Returns:
            Diagnosis dict with category, description, severity, suggested_fix
        """
        # Build diagnosis prompt
        prompt = self._build_diagnosis_prompt(context, network_logs)
        
        try:
            if GENAI_NEW_API:
                # New API
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=[
                        {
                            "role": "user",
                            "parts": [
                                {"text": prompt},
                                {
                                    "inline_data": {
                                        "mime_type": "image/png",
                                        "data": screenshot_base64
                                    }
                                }
                            ]
                        }
                    ]
                )
                response_text = response.text
            else:
                # Old API
                image_data = {
                    'mime_type': 'image/png',
                    'data': screenshot_base64
                }
                response = self.model.generate_content([prompt, image_data])
                response_text = response.text
            
            diagnosis = self._parse_diagnosis(response_text)
            logger.info(f"Diagnosis: {diagnosis['category']} - Severity: {diagnosis['severity']}")
            
            return diagnosis
            
        except Exception as e:
            logger.error(f"Failed to diagnose failure: {e}")
            return {
                "category": "Unknown",
                "description": f"Unable to diagnose: {str(e)}",
                "severity": "P2",
                "suggested_fix": "Manual investigation required"
            }
    
    def _build_navigation_prompt(self, objective: str, persona: str) -> str:
        """Build the navigation prompt for Gemini"""
        
        persona_descriptions = {
            "normal_user": "You are a typical user who reads carefully and follows expected patterns.",
            "confused_first_timer": "You are a confused first-time user who doesn't know the happy path. You might hesitate or look for clear guidance.",
            "impatient_user": "You are an impatient user who wants to complete tasks quickly and might skip optional steps.",
            "elderly_user": "You are an elderly user who prefers large, clear buttons and simple language."
        }
        
        persona_desc = persona_descriptions.get(persona, persona_descriptions["normal_user"])
        
        return f"""You are a QA automation bot analyzing a mobile app screenshot.

PERSONA: {persona_desc}

OBJECTIVE: {objective}

TASK: Analyze the screenshot and determine the next action to accomplish the objective.

RULES:
1. You can ONLY interact via coordinates - no CSS selectors or DOM inspection
2. For clickable elements, provide the bounding box in format [ymin, xmin, ymax, xmax] on a 0-1000 scale
3. If you need to type text, first identify the input field location
4. If the objective is complete, respond with action "done"
5. If you're stuck or see an error, respond with action "stuck"

RESPONSE FORMAT (JSON):
{{
  "action_type": "click|type|scroll|wait|done|stuck",
  "bounding_box": [ymin, xmin, ymax, xmax],
  "text_to_type": "text content if action is type",
  "reasoning": "Brief explanation of why you're taking this action",
  "confidence": 0.0-1.0
}}

Analyze the screenshot and respond with JSON only."""
    
    def _build_diagnosis_prompt(self, context: str, network_logs: Optional[List[dict]]) -> str:
        """Build the diagnosis prompt"""
        
        network_context = ""
        if network_logs:
            network_context = "\n\nRECENT NETWORK ACTIVITY:\n"
            for log in network_logs[-5:]:  # Last 5 requests
                network_context += f"- {log.get('method', 'GET')} {log.get('url', 'unknown')} → {log.get('status', 'unknown')}\n"
        
        return f"""Analyze this failure screenshot and diagnose the issue.

CONTEXT: {context}
{network_context}

CATEGORIZE THE ISSUE:
- Server Error: 500, 503, API down
- Client Error: 400, 404, invalid input
- UI Glitch: overlapping elements, broken layout
- Copy Ambiguity: unclear instructions, missing labels
- Unresponsive Element: click has no effect

ASSIGN SEVERITY:
- P0 (Critical): Complete flow blocker, affects all users
- P1 (High): Major friction, affects >50% of users
- P2 (Medium): Moderate issue, workaround exists
- P3 (Low): Minor cosmetic issue

RESPONSE FORMAT (JSON):
{{
  "category": "Server Error|Client Error|UI Glitch|Copy Ambiguity|Unresponsive Element",
  "description": "Detailed description of the issue",
  "severity": "P0|P1|P2|P3",
  "suggested_fix": "Actionable recommendation"
}}

Respond with JSON only."""
    
    def _parse_response(self, response_text: str) -> NavigationAction:
        """Parse Gemini response into NavigationAction"""
        try:
            # Try to extract JSON from response
            # Gemini might wrap it in markdown code blocks
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            
            data = json.loads(response_text)
            
            return NavigationAction(
                action_type=data.get('action_type', 'stuck'),
                bounding_box=data.get('bounding_box'),
                text_to_type=data.get('text_to_type'),
                reasoning=data.get('reasoning', ''),
                confidence=data.get('confidence', 0.5)
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.debug(f"Response text: {response_text}")
            
            return NavigationAction(
                action_type="stuck",
                reasoning="Failed to parse AI response"
            )
    
    def _parse_diagnosis(self, response_text: str) -> Dict[str, Any]:
        """Parse diagnosis response"""
        try:
            # Extract JSON
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            
            return json.loads(response_text)
            
        except json.JSONDecodeError:
            return {
                "category": "Unknown",
                "description": response_text[:200],
                "severity": "P2",
                "suggested_fix": "Review response manually"
            }
