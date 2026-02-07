"""
Test Case Data Models
Defines TestCase and TestCaseResult dataclasses for prompt-driven testing
"""

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, List
from enum import Enum


class TestStatus(str, Enum):
    """Possible test run outcomes"""
    PASS = "PASS"
    FAIL = "FAIL"
    STUCK = "STUCK"
    TIMEOUT = "TIMEOUT"
    ERROR = "ERROR"


@dataclass
class TestCase:
    """
    A reusable test case with natural language objective
    """
    id: str                           # UUID
    name: str                         # Human-readable label
    objective: str                    # Natural language prompt
    target_url: str                   # Starting URL
    persona: str                      # Persona key (e.g. "normal_user")
    created_at: datetime
    last_run: Optional[datetime] = None
    run_count: int = 0
    last_result: Optional[str] = None  # TestStatus value
    tags: List[str] = field(default_factory=list)
    max_steps: int = 30
    use_browserless: bool = True      # Whether to use Docker Browserless
    
    @classmethod
    def create(
        cls,
        name: str,
        objective: str,
        target_url: str,
        persona: str = "normal_user",
        tags: Optional[List[str]] = None,
        max_steps: int = 30,
        use_browserless: bool = True
    ) -> "TestCase":
        """Factory method to create a new test case"""
        return cls(
            id=str(uuid.uuid4()),
            name=name,
            objective=objective,
            target_url=target_url,
            persona=persona,
            created_at=datetime.now(),
            tags=tags or [],
            max_steps=max_steps,
            use_browserless=use_browserless
        )
    
    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict"""
        data = asdict(self)
        data['created_at'] = self.created_at.isoformat()
        data['last_run'] = self.last_run.isoformat() if self.last_run else None
        return data
    
    @classmethod
    def from_dict(cls, data: dict) -> "TestCase":
        """Create from dict"""
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        if data.get('last_run'):
            data['last_run'] = datetime.fromisoformat(data['last_run'])
        return cls(**data)


@dataclass
class TestCaseResult:
    """
    Result of a single test case run
    """
    test_case_id: str
    run_id: str
    timestamp: datetime
    status: str                       # TestStatus value
    steps_taken: int
    issues_found: List[dict]          # Serialized issue dicts
    duration_seconds: float
    screenshots: List[str] = field(default_factory=list)  # Paths to screenshots
    error_message: Optional[str] = None
    
    @classmethod
    def create(
        cls,
        test_case_id: str,
        status: str,
        steps_taken: int,
        issues_found: List[dict],
        duration_seconds: float,
        screenshots: Optional[List[str]] = None,
        error_message: Optional[str] = None
    ) -> "TestCaseResult":
        """Factory method to create a new result"""
        return cls(
            test_case_id=test_case_id,
            run_id=str(uuid.uuid4()),
            timestamp=datetime.now(),
            status=status,
            steps_taken=steps_taken,
            issues_found=issues_found,
            duration_seconds=duration_seconds,
            screenshots=screenshots or [],
            error_message=error_message
        )
    
    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: dict) -> "TestCaseResult":
        """Create from dict"""
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)
