"""
Reading progress manager for tracking page positions across sessions.
Stores progress in JSON file for persistence.
"""

import json
import os
import logging
from datetime import datetime
from typing import Optional, Dict
import threading


class ProgressManager:
    """
    Manage reading progress persistence for books
    """
    
    def __init__(self, progress_file: str = "data/reading_progress.json"):
        """
        Initialize progress manager
        
        Args:
            progress_file: Path to JSON file for storing progress
        """
        self.logger = logging.getLogger(__name__)
        self.progress_file = progress_file
        self.lock = threading.Lock()
        
        # Ensure data directory exists
        os.makedirs(os.path.dirname(progress_file), exist_ok=True)
        
        # Load existing progress
        self.progress_data = self._load_progress_file()
    
    def _load_progress_file(self) -> Dict:
        """Load progress data from JSON file"""
        if not os.path.exists(self.progress_file):
            self.logger.info(f"No existing progress file, creating new one")
            return {}
        
        try:
            with open(self.progress_file, 'r') as f:
                data = json.load(f)
                self.logger.info(f"Loaded progress for {len(data)} books")
                return data
        except Exception as e:
            self.logger.error(f"Failed to load progress file: {e}")
            return {}
    
    def _save_progress_file(self):
        """Save progress data to JSON file"""
        try:
            with open(self.progress_file, 'w') as f:
                json.dump(self.progress_data, f, indent=2)
            self.logger.debug(f"Saved progress to {self.progress_file}")
        except Exception as e:
            self.logger.error(f"Failed to save progress file: {e}")
    
    def save_progress(self, book_path: str, current_page: int, total_pages: int):
        """
        Save reading progress for a book
        
        Args:
            book_path: Full path to the book file
            current_page: Current page number (0-indexed)
            total_pages: Total number of pages in book
        """
        with self.lock:
            # Normalize path
            book_path = os.path.abspath(book_path)
            
            # Update progress data
            self.progress_data[book_path] = {
                'current_page': current_page,
                'total_pages': total_pages,
                'last_read': datetime.now().isoformat()
            }
            
            # Save to file
            self._save_progress_file()
            
            self.logger.info(f"📖 Saved progress: {os.path.basename(book_path)} - Page {current_page + 1}/{total_pages}")
    
    def load_progress(self, book_path: str) -> Optional[int]:
        """
        Load saved progress for a book
        
        Args:
            book_path: Full path to the book file
            
        Returns:
            Last page number (0-indexed) or None if no progress saved
        """
        with self.lock:
            # Normalize path
            book_path = os.path.abspath(book_path)
            
            if book_path in self.progress_data:
                progress = self.progress_data[book_path]
                page = progress['current_page']
                total = progress['total_pages']
                self.logger.info(f"📚 Restored progress: {os.path.basename(book_path)} - Page {page + 1}/{total}")
                return page
            else:
                self.logger.debug(f"No saved progress for {os.path.basename(book_path)}")
                return None
    
    def clear_progress(self, book_path: str):
        """
        Clear saved progress for a book
        
        Args:
            book_path: Full path to the book file
        """
        with self.lock:
            # Normalize path
            book_path = os.path.abspath(book_path)
            
            if book_path in self.progress_data:
                del self.progress_data[book_path]
                self._save_progress_file()
                self.logger.info(f"Cleared progress for {os.path.basename(book_path)}")
    
    def get_all_progress(self) -> Dict:
        """
        Get all saved progress data
        
        Returns:
            Dictionary of all book progress
        """
        with self.lock:
            return self.progress_data.copy()
    
    def clear_all_progress(self):
        """Clear all saved progress"""
        with self.lock:
            self.progress_data = {}
            self._save_progress_file()
            self.logger.info("Cleared all reading progress")
