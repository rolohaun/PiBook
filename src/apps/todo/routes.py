"""
To-Do List API Routes

Flask Blueprint for To-Do list REST API endpoints.
"""

import uuid
import datetime
import logging
from flask import Blueprint, jsonify, request

# Create Blueprint
todo_bp = Blueprint('todo', __name__)
logger = logging.getLogger(__name__)

# TodoManager instance will be set by webserver
todo_manager = None


def init_routes(manager):
    """
    Initialize routes with TodoManager instance
    
    Args:
        manager: TodoManager instance
    """
    global todo_manager
    todo_manager = manager
    logger.info("Initialized To-Do routes")


@todo_bp.route('/api/todos', methods=['GET'])
def get_todos():
    """Get all to-do tasks"""
    try:
        todos = todo_manager.load_todos()
        return jsonify(todos)
    except Exception as e:
        logger.error(f"Failed to load todos: {e}")
        return jsonify({'error': str(e)}), 500


@todo_bp.route('/api/todos', methods=['POST'])
def add_todo():
    """Add a new to-do task"""
    try:
        data = request.get_json()
        task_text = data.get('text', '').strip()
        
        if not task_text:
            return jsonify({'error': 'Task text is required'}), 400
        
        todos = todo_manager.load_todos()
        
        # Generate new task
        new_task = {
            'id': str(uuid.uuid4()),
            'text': task_text,
            'completed': False,
            'created_at': datetime.datetime.now().isoformat()
        }
        
        todos['tasks'].append(new_task)
        todo_manager.save_todos(todos)
        todo_manager.refresh_screen()
        
        logger.info(f"Added todo: {task_text}")
        return jsonify({'success': True, 'task': new_task})
        
    except Exception as e:
        logger.error(f"Failed to add todo: {e}")
        return jsonify({'error': str(e)}), 500


@todo_bp.route('/api/todos/<task_id>', methods=['PUT'])
def toggle_todo(task_id):
    """Toggle task completion status"""
    try:
        todos = todo_manager.load_todos()
        
        for task in todos['tasks']:
            if task['id'] == task_id:
                task['completed'] = not task['completed']
                todo_manager.save_todos(todos)
                todo_manager.refresh_screen()
                logger.info(f"Toggled todo {task_id}: {task['completed']}")
                return jsonify({'success': True, 'task': task})
        
        return jsonify({'error': 'Task not found'}), 404
        
    except Exception as e:
        logger.error(f"Failed to toggle todo: {e}")
        return jsonify({'error': str(e)}), 500


@todo_bp.route('/api/todos/<task_id>', methods=['PATCH'])
def edit_todo(task_id):
    """Edit task text"""
    try:
        data = request.get_json()
        new_text = data.get('text', '').strip()
        
        if not new_text:
            return jsonify({'error': 'Task text is required'}), 400
        
        todos = todo_manager.load_todos()
        
        for task in todos['tasks']:
            if task['id'] == task_id:
                task['text'] = new_text
                todo_manager.save_todos(todos)
                todo_manager.refresh_screen()
                logger.info(f"Edited todo {task_id}: {new_text}")
                return jsonify({'success': True, 'task': task})
        
        return jsonify({'error': 'Task not found'}), 404
        
    except Exception as e:
        logger.error(f"Failed to edit todo: {e}")
        return jsonify({'error': str(e)}), 500


@todo_bp.route('/api/todos/<task_id>', methods=['DELETE'])
def delete_todo(task_id):
    """Delete a to-do task"""
    try:
        todos = todo_manager.load_todos()
        initial_count = len(todos['tasks'])
        
        todos['tasks'] = [t for t in todos['tasks'] if t['id'] != task_id]
        
        if len(todos['tasks']) < initial_count:
            todo_manager.save_todos(todos)
            todo_manager.refresh_screen()
            logger.info(f"Deleted todo {task_id}")
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Task not found'}), 404
            
    except Exception as e:
        logger.error(f"Failed to delete todo: {e}")
        return jsonify({'error': str(e)}), 500


@todo_bp.route('/remote/open_todo', methods=['POST'])
def open_todo():
    """Open To-Do app on PiBook"""
    try:
        # Get app instance from todo_manager
        if not todo_manager or not todo_manager.app_instance:
            return jsonify({'error': 'App instance not available'}), 500
        
        # Navigate to To-Do screen
        from src.ui.navigation import Screen
        todo_manager.app_instance.navigation.navigate_to(Screen.TODO)
        todo_manager.app_instance._render_current_screen()
        logger.info("Opened To-Do app from web interface")
        return jsonify({'success': True})
        
    except Exception as e:
        logger.error(f"Failed to open To-Do app: {e}")
        return jsonify({'error': str(e)}), 500
