"""
Test Case Storage
JSON-file-based persistence for test cases and run history
"""

import json
import logging
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from .test_case_model import TestCase, TestCaseResult

logger = logging.getLogger(__name__)


class TestCaseStore:
    """
    Manages test case persistence to JSON files
    
    Directory structure:
    testcases/
    ├── saved/           # Test case definitions
    │   ├── {id}.json
    │   └── ...
    └── results/         # Run history
        ├── {tc_id}/
        │   ├── {run_id}.json
        │   └── ...
        └── ...
    """
    
    def __init__(self, base_dir: str = "testcases"):
        self.base_dir = Path(base_dir)
        self.saved_dir = self.base_dir / "saved"
        self.results_dir = self.base_dir / "results"
        self._ensure_dirs()
    
    def _ensure_dirs(self):
        """Create directories if they don't exist"""
        self.saved_dir.mkdir(parents=True, exist_ok=True)
        self.results_dir.mkdir(parents=True, exist_ok=True)
    
    # ==========================================
    # Test Case CRUD
    # ==========================================
    
    def save_test_case(self, test_case: TestCase) -> bool:
        """Save a test case to disk"""
        try:
            filepath = self.saved_dir / f"{test_case.id}.json"
            with open(filepath, 'w') as f:
                json.dump(test_case.to_dict(), f, indent=2)
            logger.info(f"Saved test case: {test_case.name} ({test_case.id})")
            return True
        except Exception as e:
            logger.error(f"Failed to save test case: {e}")
            return False
    
    def load_test_case(self, test_case_id: str) -> Optional[TestCase]:
        """Load a test case by ID"""
        try:
            filepath = self.saved_dir / f"{test_case_id}.json"
            if not filepath.exists():
                return None
            with open(filepath, 'r') as f:
                data = json.load(f)
            return TestCase.from_dict(data)
        except Exception as e:
            logger.error(f"Failed to load test case {test_case_id}: {e}")
            return None
    
    def list_test_cases(self) -> List[TestCase]:
        """List all saved test cases"""
        test_cases = []
        try:
            for filepath in self.saved_dir.glob("*.json"):
                try:
                    with open(filepath, 'r') as f:
                        data = json.load(f)
                    test_cases.append(TestCase.from_dict(data))
                except Exception as e:
                    logger.warning(f"Failed to load {filepath}: {e}")
        except Exception as e:
            logger.error(f"Failed to list test cases: {e}")
        
        # Sort by creation date, newest first
        test_cases.sort(key=lambda tc: tc.created_at, reverse=True)
        return test_cases
    
    def delete_test_case(self, test_case_id: str) -> bool:
        """Delete a test case and its history"""
        try:
            # Delete the test case file
            filepath = self.saved_dir / f"{test_case_id}.json"
            if filepath.exists():
                filepath.unlink()
            
            # Delete results directory
            results_path = self.results_dir / test_case_id
            if results_path.exists():
                for f in results_path.glob("*.json"):
                    f.unlink()
                results_path.rmdir()
            
            logger.info(f"Deleted test case: {test_case_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete test case {test_case_id}: {e}")
            return False
    
    def update_test_case(self, test_case: TestCase) -> bool:
        """Update an existing test case"""
        return self.save_test_case(test_case)
    
    # ==========================================
    # Test Results
    # ==========================================
    
    def save_result(self, result: TestCaseResult) -> bool:
        """Save a test run result"""
        try:
            # Create results directory for this test case
            test_dir = self.results_dir / result.test_case_id
            test_dir.mkdir(parents=True, exist_ok=True)
            
            # Save result
            filepath = test_dir / f"{result.run_id}.json"
            with open(filepath, 'w') as f:
                json.dump(result.to_dict(), f, indent=2)
            
            # Update the test case's last_run and run_count
            test_case = self.load_test_case(result.test_case_id)
            if test_case:
                test_case.last_run = result.timestamp
                test_case.run_count += 1
                test_case.last_result = result.status
                self.save_test_case(test_case)
            
            logger.info(f"Saved result for test case {result.test_case_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to save result: {e}")
            return False
    
    def get_run_history(self, test_case_id: str) -> List[TestCaseResult]:
        """Get all run results for a test case"""
        results = []
        try:
            test_dir = self.results_dir / test_case_id
            if not test_dir.exists():
                return results
            
            for filepath in test_dir.glob("*.json"):
                try:
                    with open(filepath, 'r') as f:
                        data = json.load(f)
                    results.append(TestCaseResult.from_dict(data))
                except Exception as e:
                    logger.warning(f"Failed to load result {filepath}: {e}")
        except Exception as e:
            logger.error(f"Failed to get run history: {e}")
        
        # Sort by timestamp, newest first
        results.sort(key=lambda r: r.timestamp, reverse=True)
        return results
    
    def get_latest_result(self, test_case_id: str) -> Optional[TestCaseResult]:
        """Get the most recent result for a test case"""
        history = self.get_run_history(test_case_id)
        return history[0] if history else None
    
    # ==========================================
    # Import/Export
    # ==========================================
    
    def export_all(self) -> dict:
        """Export all test cases as a JSON bundle"""
        test_cases = self.list_test_cases()
        return {
            "version": "1.0",
            "exported_at": datetime.now().isoformat(),
            "test_cases": [tc.to_dict() for tc in test_cases]
        }
    
    def import_bundle(self, data: dict) -> int:
        """
        Import test cases from a JSON bundle
        Returns count of imported test cases
        """
        imported = 0
        try:
            for tc_data in data.get("test_cases", []):
                test_case = TestCase.from_dict(tc_data)
                # Reset run stats for imported cases
                test_case.run_count = 0
                test_case.last_run = None
                test_case.last_result = None
                if self.save_test_case(test_case):
                    imported += 1
        except Exception as e:
            logger.error(f"Import failed: {e}")
        
        logger.info(f"Imported {imported} test cases")
        return imported
    
    def export_to_file(self, filepath: str) -> bool:
        """Export all test cases to a file"""
        try:
            data = self.export_all()
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Export failed: {e}")
            return False
    
    def import_from_file(self, filepath: str) -> int:
        """Import test cases from a file"""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            return self.import_bundle(data)
        except Exception as e:
            logger.error(f"Import failed: {e}")
            return 0
