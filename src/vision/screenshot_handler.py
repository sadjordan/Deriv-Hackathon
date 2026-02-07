"""
Screenshot Capture and Processing
Handles screenshot capture, base64 encoding, and bounding box overlays
"""

import base64
import os
from datetime import datetime
from pathlib import Path
from typing import Tuple, Optional, List
from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import Page
import logging

logger = logging.getLogger(__name__)


class ScreenshotHandler:
    """Handles screenshot capture and visual annotations"""
    
    def __init__(self, screenshots_dir: str = "screenshots"):
        """
        Initialize screenshot handler
        
        Args:
            screenshots_dir: Directory to save screenshots
        """
        self.screenshots_dir = Path(screenshots_dir)
        self.screenshots_dir.mkdir(exist_ok=True)
        
    def capture_state(
        self,
        page: Page,
        prefix: str = "screenshot"
    ) -> Tuple[str, str]:
        """
        Capture current page state as screenshot
        
        Args:
            page: Playwright page object
            prefix: Filename prefix for saved screenshot
            
        Returns:
            Tuple of (file_path, base64_string)
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        filename = f"{prefix}_{timestamp}.png"
        filepath = self.screenshots_dir / filename
        
        # Capture screenshot (viewport only, not full page)
        # This ensures screenshot dimensions match viewport for accurate coordinate conversion
        page.screenshot(path=str(filepath), full_page=False)
        logger.info(f"Screenshot captured: {filepath}")
        
        # Convert to base64
        with open(filepath, "rb") as image_file:
            base64_string = base64.b64encode(image_file.read()).decode('utf-8')
        
        return str(filepath), base64_string
    
    def draw_bounding_box(
        self,
        image_path: str,
        bounding_box: List[int],
        label: str = "",
        output_path: Optional[str] = None,
        color: str = "red"
    ) -> str:
        """
        Draw bounding box on image with optional label
        
        Args:
            image_path: Path to source image
            bounding_box: [ymin, xmin, ymax, xmax] in 0-1000 scale
            label: Optional text label to add
            output_path: Path to save annotated image (default: overwrite source)
            color: Box outline color (default: red)
            
        Returns:
            Path to annotated image
        """
        # Load image
        img = Image.open(image_path)
        draw = ImageDraw.Draw(img)
        
        # Get image dimensions
        width, height = img.size
        
        # Convert normalized coordinates (0-1000) to pixels
        ymin, xmin, ymax, xmax = bounding_box
        x1 = int((xmin / 1000) * width)
        y1 = int((ymin / 1000) * height)
        x2 = int((xmax / 1000) * width)
        y2 = int((ymax / 1000) * height)
        
        # Draw rectangle
        draw.rectangle(
            [(x1, y1), (x2, y2)],
            outline=color,
            width=3
        )
        
        # Add label if provided
        if label:
            try:
                # Try to use a nice font
                font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 16)
            except:
                # Fallback to default
                font = ImageFont.load_default()
            
            # Draw label background
            text_bbox = draw.textbbox((x1, y1 - 20), label, font=font)
            draw.rectangle(text_bbox, fill=color)
            draw.text((x1, y1 - 20), label, fill="white", font=font)
        
        # Save annotated image
        if output_path is None:
            output_path = image_path
        
        img.save(output_path)
        logger.info(f"Bounding box drawn on {output_path}")
        
        return output_path
    
    def draw_multiple_boxes(
        self,
        image_path: str,
        boxes: List[dict],
        output_path: Optional[str] = None
    ) -> str:
        """
        Draw multiple bounding boxes on image
        
        Args:
            image_path: Path to source image
            boxes: List of dicts with keys: bbox (list), label (str), color (str)
            output_path: Path to save annotated image
            
        Returns:
            Path to annotated image
        """
        img = Image.open(image_path)
        draw = ImageDraw.Draw(img)
        width, height = img.size
        
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 14)
        except:
            font = ImageFont.load_default()
        
        for i, box_data in enumerate(boxes):
            bbox = box_data.get('bbox', [])
            label = box_data.get('label', f'Element {i+1}')
            color = box_data.get('color', 'red')
            
            # Convert coordinates
            ymin, xmin, ymax, xmax = bbox
            x1 = int((xmin / 1000) * width)
            y1 = int((ymin / 1000) * height)
            x2 = int((xmax / 1000) * width)
            y2 = int((ymax / 1000) * height)
            
            # Draw box
            draw.rectangle([(x1, y1), (x2, y2)], outline=color, width=2)
            
            # Draw label
            if label:
                text_bbox = draw.textbbox((x1, max(0, y1 - 18)), label, font=font)
                draw.rectangle(text_bbox, fill=color)
                draw.text((x1, max(0, y1 - 18)), label, fill="white", font=font)
        
        # Save
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = str(self.screenshots_dir / f"annotated_{timestamp}.png")
        
        img.save(output_path)
        logger.info(f"Multiple boxes drawn on {output_path}")
        
        return output_path
    
    def calculate_center(self, bounding_box: List[int], viewport_size: dict) -> Tuple[int, int]:
        """
        Calculate center pixel coordinates from bounding box
        
        Args:
            bounding_box: [ymin, xmin, ymax, xmax] in 0-1000 scale
            viewport_size: {'width': int, 'height': int}
            
        Returns:
            Tuple of (x, y) pixel coordinates
        """
        ymin, xmin, ymax, xmax = bounding_box
        width = viewport_size['width']
        height = viewport_size['height']
        
        # Convert to pixel coordinates
        x1 = (xmin / 1000) * width
        x2 = (xmax / 1000) * width
        y1 = (ymin / 1000) * height
        y2 = (ymax / 1000) * height
        
        # Calculate center
        center_x = int((x1 + x2) / 2)
        center_y = int((y1 + y2) / 2)
        
        return center_x, center_y
    
    def validate_coordinates(self, x: int, y: int, viewport_size: dict) -> bool:
        """
        Validate that coordinates are within viewport
        
        Args:
            x: X coordinate
            y: Y coordinate
            viewport_size: {'width': int, 'height': int}
            
        Returns:
            True if coordinates are valid
        """
        width = viewport_size['width']
        height = viewport_size['height']
        
        return 0 <= x <= width and 0 <= y <= height
