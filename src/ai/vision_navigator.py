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
    action_type: str  # 'click', 'type', 'press_key', 'scroll', 'go_back', 'wait', 'done', 'stuck'
    bounding_box: Optional[List[int]] = None  # [ymin, xmin, ymax, xmax] in 0-1000 scale
    text_to_type: Optional[str] = None
    press_enter: bool = False  # Whether to press Enter after typing
    key_to_press: Optional[str] = None  # Key to press if action_type is 'press_key'
    scroll_direction: str = "down"  # 'up' or 'down' for scroll action
    reasoning: str = ""
    confidence: float = 0.0


class GeminiVisionNavigator:
    """AI-powered navigation using Gemini Vision"""
    
    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-2.5-flash-lite"):
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
        persona: str = "normal_user",
        website_context: str = "",
        previous_actions: List[str] = None
    ) -> NavigationAction:
        """
        Analyze screenshot and determine next action
        
        Args:
            screenshot_base64: Base64 encoded screenshot
            objective: What the agent should accomplish
            persona: User persona for context
            website_context: Context summary of the website
            previous_actions: List of previous actions taken
            
        Returns:
            NavigationAction object
        """
        # Build prompt
        prompt = self._build_navigation_prompt(objective, persona, website_context, previous_actions)
        
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
                    
                    # Check for empty response
                    if not response_text or response_text.strip() == "":
                        logger.warning(f"Empty response from Gemini on attempt {attempt + 1}")
                        if attempt < 2:
                            continue  # Retry
                        return NavigationAction(
                            action_type="wait",
                            reasoning="Empty API response - waiting before retry"
                        )
                    
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
    
    # Detailed persona profiles with personal information for form filling
    PERSONA_PROFILES = {
        "normal_user": {
            "description": "You are a typical user who reads carefully and follows expected patterns.",
            "profile": {
                "first_name": "Alex",
                "last_name": "Thompson",
                "full_name": "Alex Thompson",
                "email": "alex.thompson.test@gmail.com",
                "phone": "+1 (555) 234-5678",
                "mobile": "5552345678",
                "date_of_birth": "1990-05-15",
                "age": 35,
                "gender": "Male",
                "address": "742 Evergreen Terrace",
                "address_line_2": "Apt 4B",
                "city": "Springfield",
                "state": "Illinois",
                "zip_code": "62701",
                "country": "United States",
                "nationality": "American",
                "occupation": "Software Engineer",
                "company": "Tech Solutions Inc.",
                "annual_income": "$75,000 - $100,000",
                "password": "TestPass123!",
                "username": "alex_thompson_90",
                "ssn_last4": "1234",
                "card_number": "4111111111111111",
                "card_expiry": "12/28",
                "card_cvv": "123"
            }
        },
        "confused_first_timer": {
            "description": "You are a confused first-time user who doesn't know the happy path. You might hesitate or look for clear guidance.",
            "profile": {
                "first_name": "Maria",
                "last_name": "Garcia",
                "full_name": "Maria Garcia",
                "email": "maria.garcia.newuser@yahoo.com",
                "phone": "+1 (555) 876-5432",
                "mobile": "5558765432",
                "date_of_birth": "1985-11-22",
                "age": 40,
                "gender": "Female",
                "address": "123 Oak Street",
                "address_line_2": "",
                "city": "Austin",
                "state": "Texas",
                "zip_code": "78701",
                "country": "United States",
                "nationality": "Mexican-American",
                "occupation": "Teacher",
                "company": "Austin Public Schools",
                "annual_income": "$50,000 - $75,000",
                "password": "NewUser2024!",
                "username": "maria_g_85",
                "ssn_last4": "5678",
                "card_number": "5500000000000004",
                "card_expiry": "06/27",
                "card_cvv": "456"
            }
        },
        "impatient_user": {
            "description": "You are an impatient user who wants to complete tasks quickly and might skip optional steps.",
            "profile": {
                "first_name": "James",
                "last_name": "Chen",
                "full_name": "James Chen",
                "email": "jchen.fast@outlook.com",
                "phone": "+1 (555) 111-2222",
                "mobile": "5551112222",
                "date_of_birth": "1995-03-08",
                "age": 30,
                "gender": "Male",
                "address": "555 Rush Lane",
                "address_line_2": "Suite 100",
                "city": "San Francisco",
                "state": "California",
                "zip_code": "94102",
                "country": "United States",
                "nationality": "Chinese-American",
                "occupation": "Day Trader",
                "company": "Self-Employed",
                "annual_income": "$100,000 - $150,000",
                "password": "QuickPass99!",
                "username": "jchen_speedster",
                "ssn_last4": "9012",
                "card_number": "378282246310005",
                "card_expiry": "09/26",
                "card_cvv": "7890"
            }
        },
        "elderly_user": {
            "description": "You are an elderly user who prefers large, clear buttons and simple language.",
            "profile": {
                "first_name": "Dorothy",
                "last_name": "Williams",
                "full_name": "Dorothy Williams",
                "email": "dorothy.williams1952@aol.com",
                "phone": "+1 (555) 333-4444",
                "mobile": "5553334444",
                "date_of_birth": "1952-08-30",
                "age": 73,
                "gender": "Female",
                "address": "890 Maple Drive",
                "address_line_2": "",
                "city": "Phoenix",
                "state": "Arizona",
                "zip_code": "85001",
                "country": "United States",
                "nationality": "American",
                "occupation": "Retired",
                "company": "N/A",
                "annual_income": "$25,000 - $50,000",
                "password": "Dorothy1952!",
                "username": "dorothy_w_52",
                "ssn_last4": "3456",
                "card_number": "6011111111111117",
                "card_expiry": "03/29",
                "card_cvv": "234"
            }
        }
    }
    
    def _build_navigation_prompt(self, objective: str, persona: str, website_context: str = "", previous_actions: List[str] = None) -> str:
        """Build the navigation prompt for Gemini"""
        
        persona_data = self.PERSONA_PROFILES.get(persona, self.PERSONA_PROFILES["normal_user"])
        persona_desc = persona_data["description"]
        profile = persona_data["profile"]
        
        # Format profile as readable text for the AI
        profile_text = f"""
YOUR PERSONAL DETAILS (use these when filling forms):
- Name: {profile['full_name']}
- Email: {profile['email']}
- Phone: {profile['phone']}
- Address: {profile['address']}, {profile['city']}, {profile['state']} {profile['zip_code']}
- Username: {profile['username']}
- Password: {profile['password']}
"""

        # Format previous actions
        prev_actions_text = "None yet."
        if previous_actions and len(previous_actions) > 0:
            formatted_actions = []
            for i, action in enumerate(previous_actions[-15:]):  # Show last 15 actions
                formatted_actions.append(f"Step {len(previous_actions) - len(previous_actions[-15:]) + i + 1}: {action}")
            prev_actions_text = "\n".join(formatted_actions)
        
        return f"""You are an autonomous QA testing agent navigating a mobile website.
        
WEBSITE CONTEXT:
{website_context}

OBJECTIVE: {objective}

PERSONA: {persona_desc}
{profile_text}

PREVIOUS ACTIONS (Review carefully to avoid loops):
{prev_actions_text}

TASK: Analyze the screenshot and determine the next action to accomplish the objective.

CRITICAL - LOOP PREVENTION & STUCK HANDLING:
1. **REVIEW PREVIOUS ACTIONS**: If you see repetitive actions (e.g., scrolling down multiple times with no result, or clicking the same button twice), STOP.
2. **TRY ALTERNATIVES**:
   - If "scroll down" failed 3 times, try "scroll up" to find headers/menus.
   - If clicking a text link failed, look for an ICON instead.
   - If a form didn't submit, check for validation errors or a different "Submit" button.
3. **USE VISUAL CLUES**:
   - Look for **ICONS**: 🔍 (Search), 👤 (Profile/Login), ☰ (Menu/Hamburger), 🛒 (Cart).
   - Sign In/Login is often in the header (top right) or inside the Hamburger menu.
   - Search bars often have a magnifying glass icon or placeholder text.

COMMON UI PATTERNS:
1. **SEARCH**: Look at the TOP of the page. Click the search bar/icon, type query, press Enter.
2. **NAVIGATION**: Main menu is usually a Hamburger icon (☰) at top-left or top-right.
3. **FORMS**: Fill top-to-bottom. If no "Submit" button is visible, try pressing Enter after the last field.

RESPONSE FORMAT (JSON ONLY):
{{
  "action_type": "click|type|press_key|scroll|go_back|wait|done|stuck",
  "bounding_box": [ymin, xmin, ymax, xmax],
  "text_to_type": "text content if action is type",
  "press_enter": true/false,
  "scroll_direction": "up|down",
  "reasoning": "Brief explanation. IF REPEATING AN ACTION, EXPLAIN WHY.",
  "confidence": 0.0-1.0
}}"""
    
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
            # Handle null/empty responses
            if not response_text or not response_text.strip():
                logger.warning("Empty response text received")
                return NavigationAction(
                    action_type="wait",
                    reasoning="Empty response from AI - will retry"
                )
            
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
                press_enter=data.get('press_enter', False),
                key_to_press=data.get('key_to_press'),
                scroll_direction=data.get('scroll_direction', 'down'),
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
