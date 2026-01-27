"""Run date manager for organizing pipeline outputs by execution date."""

import os
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Tuple
from utils.logger import get_logger

logger = get_logger(__name__)


class RunDateManager:
    """
    Manages date-stamped output folders for pipeline runs.
    
    Each pipeline run (or partial run) writes all intermediate outputs into a 
    date-stamped subfolder (e.g., intermediate_outputs/20260127/).
    
    Key behaviors:
    - Full pipeline run: Creates new date folder with today's date
    - Partial run (single step): Writes to most recent incomplete folder, or creates new one
    - Ensures reproducibility by keeping all outputs from a single run together
    """
    
    # Expected subfolders for a complete pipeline run
    EXPECTED_FOLDERS = [
        '01_scrape',
        '02_deduplicate',
        '03_classify',
        '04_extract',
        '05_match_keywords',
        '06_digests'
    ]
    
    def __init__(self, base_dir: Path):
        """
        Initialize the run date manager.
        
        Args:
            base_dir: Base directory (project root), intermediate_outputs will be inside this
        """
        self.base_dir = Path(base_dir)
        self.intermediate_dir = self.base_dir / "intermediate_outputs"
        
    def get_current_run_date(self, is_full_pipeline: bool = False, step_name: Optional[str] = None) -> str:
        """
        Get the run date to use for current execution.
        
        Args:
            is_full_pipeline: True if running full pipeline, False for individual step
            step_name: Name of the step being executed (e.g., '01_scrape', '04_extract')
        
        Returns:
            Date string in YYYYMMDD format
            
        Logic:
        - Full pipeline: Always creates new date folder with today's date
        - Individual step: 
            - If most recent folder is incomplete and missing this step -> use that folder
            - Otherwise -> create new date folder with today's date
        """
        today = datetime.now().strftime('%Y%m%d')
        
        # For full pipeline, always create new date folder
        if is_full_pipeline:
            logger.info(f"Full pipeline run: creating new date folder {today}")
            return today
        
        # For individual steps, check if we should continue an existing run
        if step_name:
            existing_runs = self.list_run_dates()
            
            if existing_runs:
                most_recent = existing_runs[0]  # Already sorted newest first
                most_recent_path = self.intermediate_dir / most_recent
                
                # Check if this step already exists in the most recent run
                step_exists = (most_recent_path / step_name).exists()
                
                # Check if previous steps exist (for validation)
                step_num = int(step_name.split('_')[0])
                has_previous_steps = True
                
                if step_num > 1:
                    # Check that at least the immediately previous step exists
                    prev_step_num = step_num - 1
                    prev_step = f"{prev_step_num:02d}_{self._get_step_suffix(prev_step_num)}"
                    has_previous_steps = (most_recent_path / prev_step).exists()
                
                # Use existing folder if:
                # 1. This step doesn't exist yet (incomplete run)
                # 2. Previous steps exist (valid chain)
                if not step_exists and has_previous_steps:
                    logger.info(f"Continuing incomplete run: {most_recent}")
                    logger.info(f"Step {step_name} will be added to existing run folder")
                    return most_recent
                elif not step_exists and not has_previous_steps:
                    logger.warning(f"Most recent run {most_recent} is missing prerequisites for {step_name}")
                    logger.info(f"Creating new date folder: {today}")
                    return today
                else:
                    logger.info(f"Step {step_name} already exists in {most_recent}")
                    logger.info(f"Creating new date folder: {today}")
                    return today
            
            # No existing runs, create new one
            logger.info(f"No existing runs found, creating new date folder: {today}")
            return today
        
        # Fallback: use today's date
        return today
    
    def _get_step_suffix(self, step_num: int) -> str:
        """Get the suffix for a step number (e.g., 1 -> 'scrape')."""
        suffixes = {
            1: 'scrape',
            2: 'deduplicate',
            3: 'classify',
            4: 'extract',
            5: 'match_keywords',
            6: 'digests'
        }
        return suffixes.get(step_num, '')
    
    def get_run_folder(self, run_date: str) -> Path:
        """
        Get the full path to a run folder.
        
        Args:
            run_date: Date string in YYYYMMDD format
            
        Returns:
            Path to intermediate_outputs/YYYYMMDD/
        """
        return self.intermediate_dir / run_date
    
    def get_step_folder(self, run_date: str, step_name: str) -> Path:
        """
        Get the full path to a specific step folder within a run.
        
        Args:
            run_date: Date string in YYYYMMDD format
            step_name: Step folder name (e.g., '01_scrape', '04_extract')
            
        Returns:
            Path to intermediate_outputs/YYYYMMDD/step_name/
        """
        return self.get_run_folder(run_date) / step_name
    
    def ensure_step_folder(self, run_date: str, step_name: str) -> Path:
        """
        Ensure a step folder exists and return its path.
        
        Args:
            run_date: Date string in YYYYMMDD format
            step_name: Step folder name (e.g., '01_scrape')
            
        Returns:
            Path to the created/existing step folder
        """
        step_path = self.get_step_folder(run_date, step_name)
        step_path.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Ensured step folder exists: {step_path}")
        return step_path
    
    def list_run_dates(self) -> List[str]:
        """
        List all existing run dates, sorted newest first.
        
        Returns:
            List of date strings (YYYYMMDD format), sorted descending
        """
        if not self.intermediate_dir.exists():
            return []
        
        run_dates = []
        for item in self.intermediate_dir.iterdir():
            if item.is_dir() and len(item.name) == 8 and item.name.isdigit():
                run_dates.append(item.name)
        
        # Sort descending (newest first)
        run_dates.sort(reverse=True)
        return run_dates
    
    def get_run_status(self, run_date: str) -> Dict[str, bool]:
        """
        Get completion status of all steps in a run.
        
        Args:
            run_date: Date string in YYYYMMDD format
            
        Returns:
            Dict mapping step names to existence status
        """
        run_path = self.get_run_folder(run_date)
        
        if not run_path.exists():
            return {step: False for step in self.EXPECTED_FOLDERS}
        
        return {
            step: (run_path / step).exists()
            for step in self.EXPECTED_FOLDERS
        }
    
    def find_most_recent_incomplete_run(self) -> Optional[str]:
        """
        Find the most recent run that is incomplete.
        
        Returns:
            Run date string if found, None otherwise
        """
        run_dates = self.list_run_dates()
        
        for run_date in run_dates:
            status = self.get_run_status(run_date)
            if not all(status.values()):
                return run_date
        
        return None
    
    def get_latest_file_in_step(self, step_name: str, pattern: str = "*.json", 
                                 run_date: Optional[str] = None) -> Optional[Path]:
        """
        Find the latest file matching a pattern in a step folder.
        
        Args:
            step_name: Step folder name (e.g., '04_extract')
            pattern: File pattern to match (default: '*.json')
            run_date: Specific run date, or None to search most recent run
            
        Returns:
            Path to the latest matching file, or None if not found
        """
        if run_date is None:
            # Use most recent run
            run_dates = self.list_run_dates()
            if not run_dates:
                return None
            run_date = run_dates[0]
        
        step_path = self.get_step_folder(run_date, step_name)
        
        if not step_path.exists():
            return None
        
        matching_files = list(step_path.glob(pattern))
        
        if not matching_files:
            return None
        
        # Return the most recently modified file
        return max(matching_files, key=lambda p: p.stat().st_mtime)
    
    def validate_run_chain(self, run_date: str, up_to_step: str) -> Tuple[bool, List[str]]:
        """
        Validate that all prerequisite steps exist for a given step.
        
        Args:
            run_date: Date string in YYYYMMDD format
            up_to_step: Step to validate up to (e.g., '04_extract')
            
        Returns:
            Tuple of (is_valid, list_of_missing_steps)
        """
        step_num = int(up_to_step.split('_')[0])
        status = self.get_run_status(run_date)
        
        missing_steps = []
        for i in range(1, step_num):
            step = self.EXPECTED_FOLDERS[i - 1]
            if not status[step]:
                missing_steps.append(step)
        
        return (len(missing_steps) == 0, missing_steps)
    
    def get_step_name_from_number(self, step_number: int) -> Optional[str]:
        """
        Get step folder name from step number.
        
        Args:
            step_number: Step number (1-6)
            
        Returns:
            Step folder name or None
        """
        if 1 <= step_number <= len(self.EXPECTED_FOLDERS):
            return self.EXPECTED_FOLDERS[step_number - 1]
        return None
    
    def print_run_summary(self):
        """Print a summary of all runs and their completion status."""
        run_dates = self.list_run_dates()
        
        if not run_dates:
            logger.info("No pipeline runs found")
            return
        
        logger.info("=" * 60)
        logger.info("Pipeline Run Summary")
        logger.info("=" * 60)
        
        for run_date in run_dates:
            status = self.get_run_status(run_date)
            completed = sum(status.values())
            total = len(self.EXPECTED_FOLDERS)
            
            # Format date for display
            year, month, day = run_date[:4], run_date[4:6], run_date[6:8]
            formatted_date = f"{year}-{month}-{day}"
            
            status_str = "COMPLETE" if completed == total else f"INCOMPLETE ({completed}/{total})"
            logger.info(f"\n{formatted_date}: {status_str}")
            
            for step, exists in status.items():
                symbol = "✓" if exists else "✗"
                logger.info(f"  {symbol} {step}")
        
        logger.info("=" * 60)
