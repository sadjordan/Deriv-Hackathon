"""
Brute Force Logger - Logs every interaction during brute force exploration
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class InteractionLog:
    """Records a single interaction during brute force testing"""
    run_id: str
    screen_fingerprint: str
    element_label: str
    element_type: str
    action: str                    # click, type, scroll
    result: str                    # navigated, error, no_change, crash
    error_details: Optional[dict] = None  # Diagnosis if error
    screenshot_before: str = ""
    screenshot_after: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    response_time_ms: int = 0      # How long the page took to respond
    
    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "screen_fingerprint": self.screen_fingerprint,
            "element_label": self.element_label,
            "element_type": self.element_type,
            "action": self.action,
            "result": self.result,
            "error_details": self.error_details,
            "screenshot_before": self.screenshot_before,
            "screenshot_after": self.screenshot_after,
            "timestamp": self.timestamp.isoformat(),
            "response_time_ms": self.response_time_ms
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "InteractionLog":
        return cls(
            run_id=data["run_id"],
            screen_fingerprint=data["screen_fingerprint"],
            element_label=data["element_label"],
            element_type=data["element_type"],
            action=data["action"],
            result=data["result"],
            error_details=data.get("error_details"),
            screenshot_before=data.get("screenshot_before", ""),
            screenshot_after=data.get("screenshot_after", ""),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            response_time_ms=data.get("response_time_ms", 0)
        )
    
    def is_error(self) -> bool:
        """Check if this interaction resulted in an error"""
        return self.result in ("error", "crash")


@dataclass
class RunSummary:
    """Summary of a brute force run"""
    run_id: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    screens_visited: int = 0
    elements_tested: int = 0
    errors_found: int = 0
    crashes_found: int = 0
    new_screens_discovered: int = 0
    duration_seconds: float = 0
    
    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "screens_visited": self.screens_visited,
            "elements_tested": self.elements_tested,
            "errors_found": self.errors_found,
            "crashes_found": self.crashes_found,
            "new_screens_discovered": self.new_screens_discovered,
            "duration_seconds": self.duration_seconds
        }


class BruteForceLogger:
    """Manages logging for brute force exploration runs"""
    
    def __init__(self, log_dir: str = "brute_force_logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self.current_run_id: Optional[str] = None
        self.interactions: List[InteractionLog] = []
        self.known_issues: Set[str] = set()  # For deduplication
        self._load_known_issues()
    
    def start_run(self, run_id: str):
        """Start logging a new run"""
        self.current_run_id = run_id
        self.interactions = []
        logger.info(f"Started brute force run: {run_id}")
    
    def log_interaction(self, log: InteractionLog):
        """Log a single interaction"""
        self.interactions.append(log)
        
        # Append to run log file
        run_file = self.log_dir / f"run_{log.run_id}.jsonl"
        with open(run_file, "a") as f:
            f.write(json.dumps(log.to_dict()) + "\n")
        
        if log.is_error():
            logger.warning(f"Error on {log.element_label}: {log.result}")
    
    def end_run(self) -> RunSummary:
        """End the current run and generate summary"""
        if not self.current_run_id:
            return None
        
        # Calculate summary
        started = min(i.timestamp for i in self.interactions) if self.interactions else datetime.now()
        ended = datetime.now()
        
        summary = RunSummary(
            run_id=self.current_run_id,
            started_at=started,
            ended_at=ended,
            screens_visited=len(set(i.screen_fingerprint for i in self.interactions)),
            elements_tested=len(self.interactions),
            errors_found=sum(1 for i in self.interactions if i.result == "error"),
            crashes_found=sum(1 for i in self.interactions if i.result == "crash"),
            duration_seconds=(ended - started).total_seconds()
        )
        
        # Save summary
        summary_file = self.log_dir / f"summary_{self.current_run_id}.json"
        with open(summary_file, "w") as f:
            json.dump(summary.to_dict(), f, indent=2)
        
        logger.info(f"Run {self.current_run_id} completed: {summary.elements_tested} interactions, {summary.errors_found} errors")
        
        self.current_run_id = None
        return summary
    
    def get_run_interactions(self, run_id: str) -> List[InteractionLog]:
        """Load all interactions from a run"""
        run_file = self.log_dir / f"run_{run_id}.jsonl"
        
        if not run_file.exists():
            return []
        
        interactions = []
        with open(run_file, "r") as f:
            for line in f:
                if line.strip():
                    interactions.append(InteractionLog.from_dict(json.loads(line)))
        
        return interactions
    
    def get_new_issues(self, run_id: str) -> List[InteractionLog]:
        """Get issues from this run that haven't been seen before"""
        new_issues = []
        
        for log in self.get_run_interactions(run_id):
            if not log.is_error():
                continue
            
            # Create unique issue key
            issue_key = f"{log.screen_fingerprint}:{log.element_label}:{log.result}"
            
            if issue_key not in self.known_issues:
                self.known_issues.add(issue_key)
                new_issues.append(log)
        
        # Persist known issues
        self._save_known_issues()
        
        return new_issues
    
    def get_all_errors(self, run_id: str = None) -> List[InteractionLog]:
        """Get all error interactions, optionally for a specific run"""
        if run_id:
            interactions = self.get_run_interactions(run_id)
        else:
            interactions = self.interactions
        
        return [i for i in interactions if i.is_error()]
    
    def get_run_summary(self, run_id: str) -> Optional[RunSummary]:
        """Load a run summary"""
        summary_file = self.log_dir / f"summary_{run_id}.json"
        
        if not summary_file.exists():
            return None
        
        with open(summary_file, "r") as f:
            data = json.load(f)
        
        return RunSummary(
            run_id=data["run_id"],
            started_at=datetime.fromisoformat(data["started_at"]),
            ended_at=datetime.fromisoformat(data["ended_at"]) if data.get("ended_at") else None,
            screens_visited=data["screens_visited"],
            elements_tested=data["elements_tested"],
            errors_found=data["errors_found"],
            crashes_found=data.get("crashes_found", 0),
            new_screens_discovered=data.get("new_screens_discovered", 0),
            duration_seconds=data.get("duration_seconds", 0)
        )
    
    def list_runs(self) -> List[str]:
        """List all run IDs"""
        runs = []
        for f in self.log_dir.glob("summary_*.json"):
            run_id = f.stem.replace("summary_", "")
            runs.append(run_id)
        return sorted(runs, reverse=True)
    
    def _load_known_issues(self):
        """Load known issues for deduplication"""
        issues_file = self.log_dir / "known_issues.json"
        if issues_file.exists():
            with open(issues_file, "r") as f:
                self.known_issues = set(json.load(f))
    
    def _save_known_issues(self):
        """Save known issues"""
        issues_file = self.log_dir / "known_issues.json"
        with open(issues_file, "w") as f:
            json.dump(list(self.known_issues), f)
