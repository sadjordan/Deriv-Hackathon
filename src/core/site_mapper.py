"""
Site Mapper - Tracks discovered screens and builds navigation graph
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from .element_discovery import InteractiveElement

logger = logging.getLogger(__name__)


@dataclass
class Screen:
    """Represents a unique screen/page in the application"""
    fingerprint: str              # Perceptual hash of the screenshot
    url: str                      # URL when this screen was captured
    screenshot_path: str          # Path to representative screenshot
    elements: List[InteractiveElement] = field(default_factory=list)
    tested_elements: Set[str] = field(default_factory=set)  # Labels we've clicked
    discovered_at: datetime = field(default_factory=datetime.now)
    has_issues: bool = False      # Whether any issues found on this screen
    
    def get_untested_elements(self) -> List[InteractiveElement]:
        """Return elements that haven't been tested yet"""
        return [e for e in self.elements if e.label not in self.tested_elements]
    
    def mark_element_tested(self, element_label: str):
        """Mark an element as tested"""
        self.tested_elements.add(element_label)
    
    def get_coverage(self) -> float:
        """Calculate test coverage for this screen"""
        if not self.elements:
            return 1.0
        return len(self.tested_elements) / len(self.elements)
    
    def to_dict(self) -> dict:
        return {
            "fingerprint": self.fingerprint,
            "url": self.url,
            "screenshot_path": self.screenshot_path,
            "elements": [e.to_dict() for e in self.elements],
            "tested_elements": list(self.tested_elements),
            "discovered_at": self.discovered_at.isoformat(),
            "has_issues": self.has_issues
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Screen":
        return cls(
            fingerprint=data["fingerprint"],
            url=data["url"],
            screenshot_path=data["screenshot_path"],
            elements=[InteractiveElement.from_dict(e) for e in data.get("elements", [])],
            tested_elements=set(data.get("tested_elements", [])),
            discovered_at=datetime.fromisoformat(data["discovered_at"]),
            has_issues=data.get("has_issues", False)
        )


@dataclass
class Transition:
    """Represents a navigation transition between screens"""
    from_screen: str      # Fingerprint of source screen
    element_label: str    # Element that was clicked
    to_screen: str        # Fingerprint of destination screen
    result: str           # navigated, error, no_change, crash
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> dict:
        return {
            "from_screen": self.from_screen,
            "element_label": self.element_label,
            "to_screen": self.to_screen,
            "result": self.result,
            "timestamp": self.timestamp.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Transition":
        return cls(
            from_screen=data["from_screen"],
            element_label=data["element_label"],
            to_screen=data["to_screen"],
            result=data["result"],
            timestamp=datetime.fromisoformat(data["timestamp"])
        )


class SiteMap:
    """Tracks discovered screens and navigation graph"""
    
    def __init__(self, save_dir: str = "sitemap"):
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(parents=True, exist_ok=True)
        
        self.screens: Dict[str, Screen] = {}        # fingerprint -> Screen
        self.transitions: List[Transition] = []      # All recorded transitions
        self.exploration_queue: List[str] = []       # Fingerprints to explore next
        
    def add_screen(
        self,
        fingerprint: str,
        screenshot_path: str,
        url: str,
        elements: List[InteractiveElement]
    ) -> Screen:
        """Add a new screen to the site map"""
        if fingerprint in self.screens:
            # Update existing screen
            screen = self.screens[fingerprint]
            logger.debug(f"Screen already exists: {fingerprint[:8]}...")
            return screen
        
        # Create new screen
        screen = Screen(
            fingerprint=fingerprint,
            url=url,
            screenshot_path=screenshot_path,
            elements=elements
        )
        
        self.screens[fingerprint] = screen
        self.exploration_queue.append(fingerprint)
        
        logger.info(f"Added new screen: {fingerprint[:8]}... with {len(elements)} elements")
        return screen
    
    def add_transition(
        self,
        from_fingerprint: str,
        element_label: str,
        to_fingerprint: str,
        result: str
    ) -> Transition:
        """Record a navigation transition"""
        transition = Transition(
            from_screen=from_fingerprint,
            element_label=element_label,
            to_screen=to_fingerprint,
            result=result
        )
        
        self.transitions.append(transition)
        
        # Mark element as tested on source screen
        if from_fingerprint in self.screens:
            self.screens[from_fingerprint].mark_element_tested(element_label)
        
        logger.debug(f"Transition: {from_fingerprint[:8]} --[{element_label}]--> {to_fingerprint[:8]} ({result})")
        return transition
    
    def get_screen(self, fingerprint: str) -> Optional[Screen]:
        """Get a screen by fingerprint"""
        return self.screens.get(fingerprint)
    
    def get_untested_elements(self, fingerprint: str) -> List[InteractiveElement]:
        """Get elements that haven't been tested on a screen"""
        screen = self.screens.get(fingerprint)
        if not screen:
            return []
        return screen.get_untested_elements()
    
    def get_next_screen_to_explore(self) -> Optional[str]:
        """Get the next screen that has untested elements"""
        # First check the exploration queue
        while self.exploration_queue:
            fingerprint = self.exploration_queue[0]
            if fingerprint in self.screens:
                untested = self.get_untested_elements(fingerprint)
                if untested:
                    return fingerprint
            # No untested elements, remove from queue
            self.exploration_queue.pop(0)
        
        # Check all screens for any with untested elements
        for fingerprint, screen in self.screens.items():
            if screen.get_untested_elements():
                return fingerprint
        
        return None  # All elements tested
    
    def is_screen_known(self, fingerprint: str) -> bool:
        """Check if a screen has been discovered before"""
        return fingerprint in self.screens
    
    def get_coverage_stats(self) -> dict:
        """Calculate overall coverage statistics"""
        total_elements = 0
        tested_elements = 0
        screens_with_issues = 0
        
        for screen in self.screens.values():
            total_elements += len(screen.elements)
            tested_elements += len(screen.tested_elements)
            if screen.has_issues:
                screens_with_issues += 1
        
        coverage_pct = (tested_elements / total_elements * 100) if total_elements > 0 else 0
        
        return {
            "screens_discovered": len(self.screens),
            "total_elements": total_elements,
            "tested_elements": tested_elements,
            "coverage_percent": round(coverage_pct, 1),
            "transitions_recorded": len(self.transitions),
            "screens_with_issues": screens_with_issues,
            "screens_fully_tested": sum(
                1 for s in self.screens.values() 
                if len(s.tested_elements) == len(s.elements) and len(s.elements) > 0
            )
        }
    
    def mark_screen_has_issues(self, fingerprint: str):
        """Mark a screen as having issues"""
        if fingerprint in self.screens:
            self.screens[fingerprint].has_issues = True
    
    # ==========================================
    # Persistence
    # ==========================================
    
    def save_to_disk(self, filename: str = "sitemap.json"):
        """Save the site map to disk"""
        filepath = self.save_dir / filename
        
        data = {
            "version": "1.0",
            "saved_at": datetime.now().isoformat(),
            "screens": {fp: s.to_dict() for fp, s in self.screens.items()},
            "transitions": [t.to_dict() for t in self.transitions],
            "exploration_queue": self.exploration_queue
        }
        
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Saved site map to {filepath}")
    
    def load_from_disk(self, filename: str = "sitemap.json") -> bool:
        """Load site map from disk"""
        filepath = self.save_dir / filename
        
        if not filepath.exists():
            logger.info("No existing site map found")
            return False
        
        try:
            with open(filepath, "r") as f:
                data = json.load(f)
            
            self.screens = {
                fp: Screen.from_dict(s) 
                for fp, s in data.get("screens", {}).items()
            }
            self.transitions = [
                Transition.from_dict(t) 
                for t in data.get("transitions", [])
            ]
            self.exploration_queue = data.get("exploration_queue", [])
            
            logger.info(f"Loaded site map with {len(self.screens)} screens")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load site map: {e}")
            return False
    
    def clear(self):
        """Clear all data"""
        self.screens.clear()
        self.transitions.clear()
        self.exploration_queue.clear()
    
    # ==========================================
    # Screen Fingerprinting
    # ==========================================
    
    @staticmethod
    def generate_fingerprint(screenshot_bytes: bytes) -> str:
        """
        Generate a perceptual hash fingerprint for a screenshot.
        Uses average hash for simplicity - handles minor visual differences.
        """
        try:
            from PIL import Image
            import io
            
            # Load image
            img = Image.open(io.BytesIO(screenshot_bytes))
            
            # Convert to grayscale and resize to 16x16
            img = img.convert("L").resize((16, 16), Image.Resampling.LANCZOS)
            
            # Get pixel data
            pixels = list(img.getdata())
            
            # Calculate average
            avg = sum(pixels) / len(pixels)
            
            # Generate hash: 1 if pixel > average, 0 otherwise
            bits = "".join("1" if p > avg else "0" for p in pixels)
            
            # Convert to hex
            hash_int = int(bits, 2)
            fingerprint = format(hash_int, "064x")
            
            return fingerprint
            
        except Exception as e:
            # Fallback to simple content hash
            logger.warning(f"Perceptual hash failed, using content hash: {e}")
            return hashlib.sha256(screenshot_bytes).hexdigest()[:64]
    
    @staticmethod
    def fingerprints_similar(fp1: str, fp2: str, threshold: int = 10) -> bool:
        """
        Check if two fingerprints are similar (small hamming distance).
        Useful for matching screens with minor differences.
        """
        if len(fp1) != len(fp2):
            return False
        
        # Convert hex to binary and count differences
        try:
            int1 = int(fp1, 16)
            int2 = int(fp2, 16)
            xor = int1 ^ int2
            distance = bin(xor).count("1")
            return distance <= threshold
        except ValueError:
            return fp1 == fp2
