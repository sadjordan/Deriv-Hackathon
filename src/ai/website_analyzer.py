"""
Website Context Analyzer
Analyzes the landing page to provide high-level context for the navigation agent
"""

import logging
from typing import Dict, Any, Optional
from src.ai.vision_navigator import GeminiVisionNavigator

logger = logging.getLogger(__name__)

class WebsiteContextAnalyzer:
    """Analyzes website structure and purpose to guide navigation"""
    
    def __init__(self, navigator: GeminiVisionNavigator):
        self.navigator = navigator
        
    def analyze_landing_page(self, screenshot_base64: str, url: str) -> str:
        """
        Analyze the landing page to understand the website's nature
        
        Args:
            screenshot_base64: Base64 encoded screenshot of landing page
            url: The URL being visited
            
        Returns:
            String description of website context
        """
        prompt = f"""
        Analyze this landing page screenshot for URL: {url}
        
        Provide a brief, high-level summary to help an autonomous agent navigate this site.
        Focus on:
        1. **Site Type**: (e.g., E-commerce, SaaS, Blog, Login Portal)
        2. **Key Goals**: What would a user typically do here? (e.g., "Search for products", "Login to dashboard", "Read articles")
        3. **Critical Elements**: Where are the key navigation elements located? (e.g., "Search bar is at the top", "Login button in header", "Hamburger menu on left")
        
        Keep it concise (under 200 words) and actionable.
        """
        
        try:
            logger.info(f"Analyzing landing page context for {url}")
            
            # Use the existing navigator's client/model to generate content
            if hasattr(self.navigator, 'client') and self.navigator.client:
                # New API
                response = self.navigator.client.models.generate_content(
                    model=self.navigator.model_name,
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
                return response.text if hasattr(response, 'text') else str(response)
            else:
                # Old API
                image_data = {
                    'mime_type': 'image/png',
                    'data': screenshot_base64
                }
                if hasattr(self.navigator, 'model'):
                    response = self.navigator.model.generate_content([prompt, image_data])
                    return response.text if hasattr(response, 'text') else str(response)
                else:
                     return "No Gemini client or model available."
                
        except Exception as e:
            logger.error(f"Failed to analyze website context: {e}")
            return "Could not analyze website context. Proceed with standard navigation."
