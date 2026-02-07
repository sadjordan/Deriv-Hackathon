"""
Element Discovery - Discovers all interactive elements on a screen via Gemini Vision
"""

import logging
from dataclasses import dataclass, field
from typing import List, Tuple, Optional
import json

logger = logging.getLogger(__name__)


@dataclass
class InteractiveElement:
    """Represents an interactive element discovered on screen"""
    label: str                    # Text/description of the element
    element_type: str             # button, link, input, dropdown, toggle, tab, other
    bounding_box: List[int]       # [ymin, xmin, ymax, xmax] (0-1000 scale)
    priority: str = "medium"      # high, medium, low
    center: Tuple[int, int] = field(default=(0, 0))  # Calculated pixel coords
    tested: bool = False          # Whether this element has been tested
    
    def calculate_center(self, viewport_width: int, viewport_height: int) -> Tuple[int, int]:
        """Convert bounding box to center pixel coordinates"""
        if len(self.bounding_box) != 4:
            return (0, 0)
        
        ymin, xmin, ymax, xmax = self.bounding_box
        
        # Convert 0-1000 scale to pixels
        center_x = int(((xmin + xmax) / 2) * viewport_width / 1000)
        center_y = int(((ymin + ymax) / 2) * viewport_height / 1000)
        
        self.center = (center_x, center_y)
        return self.center
    
    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "element_type": self.element_type,
            "bounding_box": self.bounding_box,
            "priority": self.priority,
            "center": list(self.center),
            "tested": self.tested
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "InteractiveElement":
        return cls(
            label=data.get("label", "Unknown"),
            element_type=data.get("element_type", "other"),
            bounding_box=data.get("bounding_box", [0, 0, 0, 0]),
            priority=data.get("priority", "medium"),
            center=tuple(data.get("center", [0, 0])),
            tested=data.get("tested", False)
        )


class ElementDiscovery:
    """Discovers interactive elements on screen using Gemini Vision"""
    
    DISCOVERY_PROMPT = """Analyze this mobile app screenshot and identify ALL interactive elements.

For each clickable or interactive element, provide:
- label: The text on the element or a short description
- type: One of: button, link, input, dropdown, toggle, tab, icon, menu, other
- bounding_box: [ymin, xmin, ymax, xmax] coordinates on a 0-1000 scale
- priority: high (primary actions), medium (secondary), low (minor/hidden)

Include:
- Buttons and links
- Input fields and text areas
- Dropdowns and selectors
- Toggle switches and checkboxes
- Tab bars and navigation items
- Icons that appear clickable
- Menu items

Return ONLY a JSON array of elements. Example:
[
  {"label": "Sign Up", "type": "button", "bounding_box": [800, 100, 880, 900], "priority": "high"},
  {"label": "Email input", "type": "input", "bounding_box": [300, 50, 360, 950], "priority": "high"}
]

If no interactive elements are found, return an empty array: []"""

    def __init__(self, vision_navigator):
        """
        Args:
            vision_navigator: GeminiVisionNavigator instance for API calls
        """
        self.navigator = vision_navigator
    
    def discover_elements(
        self,
        screenshot_base64: str,
        viewport_size: dict = None
    ) -> List[InteractiveElement]:
        """
        Discover all interactive elements on the current screen
        
        Args:
            screenshot_base64: Base64-encoded screenshot
            viewport_size: Dict with 'width' and 'height' keys
            
        Returns:
            List of InteractiveElement objects
        """
        if viewport_size is None:
            viewport_size = {"width": 390, "height": 844}  # iPhone 13 default
        
        try:
            # Call Gemini to analyze the screenshot
            response = self._call_gemini(screenshot_base64)
            
            # Parse response into elements
            elements = self._parse_response(response)
            
            # Calculate pixel centers
            for element in elements:
                element.calculate_center(
                    viewport_size["width"],
                    viewport_size["height"]
                )
            
            logger.info(f"Discovered {len(elements)} interactive elements")
            return elements
            
        except Exception as e:
            logger.error(f"Element discovery failed: {e}")
            return []
    
    def _call_gemini(self, screenshot_base64: str) -> str:
        """Send discovery prompt to Gemini"""
        try:
            # Use same dict format as vision_navigator
            response = self.navigator.client.models.generate_content(
                model=self.navigator.model_name,
                contents=[
                    {
                        "role": "user",
                        "parts": [
                            {"text": self.DISCOVERY_PROMPT},
                            {
                                "inline_data": {
                                    "mime_type": "image/png",
                                    "data": self._clean_base64(screenshot_base64)
                                }
                            }
                        ]
                    }
                ]
            )
            
            return response.text
            
        except Exception as e:
            logger.error(f"Gemini API call failed: {e}")
            raise
    
    def _clean_base64(self, base64_string: str) -> str:
        """Clean base64 string - remove data URL prefix if present"""
        if "," in base64_string:
            return base64_string.split(",")[1]
        return base64_string
    
    def _decode_base64(self, base64_string: str) -> bytes:
        """Decode base64 string to bytes"""
        import base64
        # Remove data URL prefix if present
        if "," in base64_string:
            base64_string = base64_string.split(",")[1]
        return base64.b64decode(base64_string)
    
    def _parse_response(self, response: str) -> List[InteractiveElement]:
        """Parse Gemini response into element list"""
        elements = []
        
        try:
            # Clean the response - extract JSON array
            text = response.strip()
            
            # Find JSON array in response
            start = text.find("[")
            end = text.rfind("]") + 1
            
            if start == -1 or end == 0:
                logger.warning("No JSON array found in response")
                return []
            
            json_str = text[start:end]
            data = json.loads(json_str)
            
            for item in data:
                if not isinstance(item, dict):
                    continue
                    
                # Validate required fields
                if "bounding_box" not in item:
                    continue
                
                element = InteractiveElement(
                    label=item.get("label", "Unknown"),
                    element_type=item.get("type", "other"),
                    bounding_box=item.get("bounding_box", [0, 0, 0, 0]),
                    priority=item.get("priority", "medium")
                )
                elements.append(element)
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
        except Exception as e:
            logger.error(f"Failed to parse response: {e}")
        
        return elements
    
    def deduplicate_elements(
        self,
        elements: List[InteractiveElement],
        existing: List[InteractiveElement],
        threshold: float = 0.8
    ) -> List[InteractiveElement]:
        """
        Remove elements that already exist (based on bounding box overlap)
        
        Args:
            elements: New elements to check
            existing: Already known elements
            threshold: IOU threshold for considering elements identical
            
        Returns:
            List of unique new elements
        """
        unique = []
        
        for new_elem in elements:
            is_duplicate = False
            
            for old_elem in existing:
                iou = self._calculate_iou(new_elem.bounding_box, old_elem.bounding_box)
                if iou >= threshold:
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                unique.append(new_elem)
        
        return unique
    
    def _calculate_iou(self, box1: List[int], box2: List[int]) -> float:
        """Calculate Intersection over Union of two bounding boxes"""
        if len(box1) != 4 or len(box2) != 4:
            return 0.0
        
        y1_min, x1_min, y1_max, x1_max = box1
        y2_min, x2_min, y2_max, x2_max = box2
        
        # Calculate intersection
        x_left = max(x1_min, x2_min)
        y_top = max(y1_min, y2_min)
        x_right = min(x1_max, x2_max)
        y_bottom = min(y1_max, y2_max)
        
        if x_right < x_left or y_bottom < y_top:
            return 0.0
        
        intersection = (x_right - x_left) * (y_bottom - y_top)
        
        # Calculate union
        area1 = (x1_max - x1_min) * (y1_max - y1_min)
        area2 = (x2_max - x2_min) * (y2_max - y2_min)
        union = area1 + area2 - intersection
        
        if union == 0:
            return 0.0
        
        return intersection / union
