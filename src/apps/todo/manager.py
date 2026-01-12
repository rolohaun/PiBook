"""
To-Do List Manager

Handles data persistence and screen refresh for the To-Do app.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Any


class TodoManager:
    """Manages To-Do list data and persistence"""
    
    def __init__(self, app_instance=None, todos_file: str = "todos.json"):
        """
        Initialize TodoManager
        
        Args:
            app_instance: Reference to main PiBook app instance (for screen refresh)
            todos_file: Path to todos JSON file
        """
        self.app_instance = app_instance
        self.todos_file = Path(todos_file)
        self.logger = logging.getLogger(__name__)
    
    def load_todos(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Load todos from JSON file
        
        Returns:
            Dictionary with 'tasks' key containing list of todo items
        """
        try:
            if self.todos_file.exists():
                with open(self.todos_file, 'r') as f:
                    data = json.load(f)
                    # Ensure data has correct structure
                    if isinstance(data, dict) and 'tasks' in data:
                        return data
                    # Legacy format: list of tasks
                    elif isinstance(data, list):
                        return {'tasks': data}
                    else:
                        self.logger.warning(f"Invalid todos format, returning empty list")
                        return {'tasks': []}
            else:
                return {'tasks': []}
        except Exception as e:
            self.logger.error(f"Failed to load todos: {e}")
            return {'tasks': []}
    
    def save_todos(self, todos: Dict[str, List[Dict[str, Any]]]) -> bool:
        """
        Save todos to JSON file
        
        Args:
            todos: Dictionary with 'tasks' key containing list of todo items
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with open(self.todos_file, 'w') as f:
                json.dump(todos, f, indent=2)
            self.logger.debug(f"Saved {len(todos.get('tasks', []))} todos")
            return True
        except Exception as e:
            self.logger.error(f"Failed to save todos: {e}")
            return False
    
    def refresh_screen(self) -> bool:
        """
        Trigger a refresh of the To-Do screen on the e-ink display
        
        Returns:
            True if successful, False otherwise
        """
        if not self.app_instance:
            self.logger.warning("No app instance available for screen refresh")
            return False
        
        try:
            from src.ui.navigation import Screen
            
            # Only refresh if we're currently on the To-Do screen
            if self.app_instance.navigation.current_screen == Screen.TODO:
                self.app_instance._render_current_screen(force_partial=True)
                self.logger.debug("Refreshed To-Do screen")
                return True
            else:
                self.logger.debug("Not on To-Do screen, skipping refresh")
                return False
        except Exception as e:
            self.logger.error(f"Failed to refresh To-Do screen: {e}")
            return False
