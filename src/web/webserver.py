"""
Flask web server for PiBook remote control and file management.
Provides web interface for:
- Uploading/managing EPUB files
- Remote navigation (next/prev/select buttons)
- Book selection
"""

from flask import Flask, render_template, request, jsonify, send_from_directory, redirect, url_for
import os
import logging
import json
from werkzeug.utils import secure_filename
from pathlib import Path


class PiBookWebServer:
    """
    Web server for remote control and file management
    """

    def __init__(self, books_dir: str, app_instance, port: int = 5000):
        """
        Initialize web server

        Args:
            books_dir: Path to books directory
            app_instance: PiBookApp instance for remote control
            port: Port to run server on
        """
        self.logger = logging.getLogger(__name__)
        self.books_dir = books_dir
        self.app_instance = app_instance
        self.port = port
        
        # Configure Flask with template and static folders
        template_dir = os.path.join(os.path.dirname(__file__), 'templates')
        static_dir = os.path.join(os.path.dirname(__file__), 'static')
        self.flask_app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
        self.flask_app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max file size

        self._setup_routes()

    def _setup_routes(self):
        """Setup Flask routes"""

        @self.flask_app.route('/')
        def index():
            """Main page with file manager and controls"""
            settings_data = self._load_settings('settings.json')
            return render_template('base.html', books=self._get_books(), settings=settings_data)

        @self.flask_app.route('/upload', methods=['POST'])
        def upload():
            """Upload EPUB file(s)"""
            if 'file' not in request.files:
                return jsonify({'error': 'No file uploaded'}), 400

            files = request.files.getlist('file')
            if not files or files[0].filename == '':
                return jsonify({'error': 'No files selected'}), 400

            uploaded_count = 0
            for file in files:
                if file and file.filename.lower().endswith('.epub'):
                    filename = secure_filename(file.filename)
                    filepath = os.path.join(self.books_dir, filename)
                    file.save(filepath)
                    self.logger.info(f"Uploaded: {filename}")
                    uploaded_count += 1

            # Reload library screen to show new books
            self.app_instance.library_screen.load_books(self.books_dir)
            # Refresh the display if on library screen
            if self.app_instance.navigation.current_screen.value == 'library':
                self.app_instance._render_current_screen()

            self.logger.info(f"Uploaded {uploaded_count} book(s)")
            return redirect(url_for('index'))

        @self.flask_app.route('/delete/<filename>')
        def delete(filename):
            """Delete EPUB file"""
            filepath = os.path.join(self.books_dir, secure_filename(filename))
            if os.path.exists(filepath) and filepath.endswith('.epub'):
                os.remove(filepath)
                self.logger.info(f"Deleted: {filename}")

                # Reload library screen to show updated book list
                self.app_instance.library_screen.load_books(self.books_dir)
                # Refresh the display if on library screen
                if self.app_instance.navigation.current_screen.value == 'library':
                    self.app_instance._render_current_screen()

            return redirect(url_for('index'))

        @self.flask_app.route('/rename', methods=['POST'])
        def rename():
            """Rename EPUB file"""
            old_name = secure_filename(request.form.get('old_name', ''))
            new_name = secure_filename(request.form.get('new_name', ''))

            if not new_name.endswith('.epub'):
                new_name += '.epub'

            old_path = os.path.join(self.books_dir, old_name)
            new_path = os.path.join(self.books_dir, new_name)

            if os.path.exists(old_path):
                os.rename(old_path, new_path)
                self.logger.info(f"Renamed: {old_name} -> {new_name}")

            return redirect(url_for('index'))

        @self.flask_app.route('/control/<action>')
        def control(action):
            """Remote control actions"""
            if action == 'next':
                self.app_instance._handle_next()
            elif action == 'prev':
                self.app_instance._handle_prev()
            elif action == 'select':
                self.app_instance._handle_select()
            elif action == 'back':
                self.app_instance._handle_back()
            elif action == 'menu':
                self.app_instance._handle_menu()

            return jsonify({'status': 'ok', 'action': action})

        # To-Do List API Routes
        @self.flask_app.route('/api/todos', methods=['GET'])
        def get_todos():
            """Get all to-do tasks"""
            try:
                todos = self._load_todos()
                return jsonify(todos)
            except Exception as e:
                self.logger.error(f"Failed to load todos: {e}")
                return jsonify({'error': str(e)}), 500

        @self.flask_app.route('/api/todos', methods=['POST'])
        def add_todo():
            """Add a new to-do task"""
            try:
                data = request.get_json()
                task_text = data.get('text', '').strip()
                
                if not task_text:
                    return jsonify({'error': 'Task text is required'}), 400
                
                todos = self._load_todos()
                
                # Generate new ID
                import uuid
                new_task = {
                    'id': str(uuid.uuid4()),
                    'text': task_text,
                    'completed': False,
                    'created_at': __import__('datetime').datetime.now().isoformat()
                }
                
                todos['tasks'].append(new_task)
                self._save_todos(todos)
                self._refresh_todo_screen()
                
                self.logger.info(f"Added todo: {task_text}")
                return jsonify({'success': True, 'task': new_task})
                
            except Exception as e:
                self.logger.error(f"Failed to add todo: {e}")
                return jsonify({'error': str(e)}), 500

        @self.flask_app.route('/api/todos/<task_id>', methods=['PUT'])
        def toggle_todo(task_id):
            """Toggle task completion status"""
            try:
                todos = self._load_todos()
                
                for task in todos['tasks']:
                    if task['id'] == task_id:
                        task['completed'] = not task['completed']
                        self._save_todos(todos)
                        self._refresh_todo_screen()
                        self.logger.info(f"Toggled todo {task_id}: {task['completed']}")
                        return jsonify({'success': True, 'task': task})
                
                return jsonify({'error': 'Task not found'}), 404
                
            except Exception as e:
                self.logger.error(f"Failed to toggle todo: {e}")
                return jsonify({'error': str(e)}), 500

        @self.flask_app.route('/api/todos/<task_id>', methods=['PATCH'])
        def edit_todo(task_id):
            """Edit task text"""
            try:
                data = request.get_json()
                new_text = data.get('text', '').strip()
                
                if not new_text:
                    return jsonify({'error': 'Task text is required'}), 400
                
                todos = self._load_todos()
                
                for task in todos['tasks']:
                    if task['id'] == task_id:
                        task['text'] = new_text
                        self._save_todos(todos)
                        self._refresh_todo_screen()
                        self.logger.info(f"Edited todo {task_id}: {new_text}")
                        return jsonify({'success': True, 'task': task})
                
                return jsonify({'error': 'Task not found'}), 404
                
            except Exception as e:
                self.logger.error(f"Failed to edit todo: {e}")
                return jsonify({'error': str(e)}), 500

        @self.flask_app.route('/api/todos/<task_id>', methods=['DELETE'])
        def delete_todo(task_id):
            """Delete a to-do task"""
            try:
                todos = self._load_todos()
                initial_count = len(todos['tasks'])
                
                todos['tasks'] = [t for t in todos['tasks'] if t['id'] != task_id]
                
                if len(todos['tasks']) < initial_count:
                    self._save_todos(todos)
                    self._refresh_todo_screen()
                    self.logger.info(f"Deleted todo {task_id}")
                    return jsonify({'success': True})
                else:
                    return jsonify({'error': 'Task not found'}), 404
                    
            except Exception as e:
                self.logger.error(f"Failed to delete todo: {e}")
                return jsonify({'error': str(e)}), 500

        @self.flask_app.route('/remote/open_todo', methods=['POST'])
        def open_todo():
            """Open To-Do app on PiBook"""
            try:
                # Navigate to To-Do screen
                from src.ui.navigation import Screen
                self.app_instance.navigation.navigate_to(Screen.TODO)
                self.app_instance._render_current_screen()
                self.logger.info("Opened To-Do app from web interface")
                return jsonify({'success': True})
            except Exception as e:
                self.logger.error(f"Failed to open To-Do app: {e}")
                return jsonify({'error': str(e)}), 500

        @self.flask_app.route('/api/cpu_voltage')
        def cpu_voltage():
            """Get current CPU voltage"""
            try:
                import subprocess
                result = subprocess.run(
                    ['vcgencmd', 'measure_volts', 'core'],
                    capture_output=True,
                    text=True,
                    timeout=2
                )
                if result.returncode == 0:
                    voltage = result.stdout.strip()
                    undervolt_setting = self.app_instance.config.get('power.undervolt', 0)
                    return jsonify({
                        'voltage': voltage,
                        'undervolt_setting': undervolt_setting,
                        'voltage_reduction_mv': abs(undervolt_setting) * 25
                    })
                else:
                    return jsonify({'error': 'Could not read voltage'}), 500
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @self.flask_app.route('/api/battery_status')
        def battery_status():
            """Get current battery status including charging state"""
            try:
                if self.app_instance.battery_monitor:
                    status = self.app_instance.battery_monitor.get_status()
                    return jsonify(status)
                else:
                    return jsonify({'error': 'Battery monitor not available'}), 503
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @self.flask_app.route('/reboot')
        def reboot():
            """Reboot the Raspberry Pi"""
            try:
                import subprocess
                self.logger.info("Reboot requested via web interface")
                # Shutdown in 5 seconds to allow response to be sent
                subprocess.Popen(['sudo', 'shutdown', '-r', '+0'])
                return jsonify({'status': 'rebooting'})
            except Exception as e:
                self.logger.error(f"Reboot failed: {e}")
                return jsonify({'error': str(e)}), 500

        @self.flask_app.route('/settings')
        def settings():
            """Settings page"""
            settings_data = self._load_settings('settings.json')
            return render_template_string(SETTINGS_TEMPLATE, settings=settings_data)

        @self.flask_app.route('/save_settings', methods=['POST'])
        def save_settings():
            """Save user settings"""
            try:
                settings_data = {
                    'zoom': float(request.form.get('zoom', 1.0)),
                    'dpi': int(request.form.get('dpi', 150)),
                    'full_refresh_interval': int(request.form.get('full_refresh_interval', 10)),
                    'show_page_numbers': request.form.get('show_page_numbers') == 'on',
                    'wifi_while_reading': request.form.get('wifi_while_reading') == 'on',
                    'sleep_enabled': request.form.get('sleep_enabled') == 'on',
                    'sleep_message': request.form.get('sleep_message', 'Shh I\'m sleeping'),
                    'sleep_timeout': int(request.form.get('sleep_timeout', 120)),
                    'items_per_page': int(request.form.get('items_per_page', 4)),
                    'undervolt': int(request.form.get('undervolt', -2))
                }

                self._save_settings(settings_data)

                # Apply settings to display driver
                self.app_instance.display.set_full_refresh_interval(settings_data['full_refresh_interval'])

                # Apply settings to reader screen if available
                if hasattr(self.app_instance.reader_screen, 'renderer') and self.app_instance.reader_screen.renderer:
                    # Reload current book with new settings
                    current_page = self.app_instance.reader_screen.current_page
                    epub_path = self.app_instance.reader_screen.epub_path
                    self.app_instance.reader_screen.close()
                    self.app_instance.reader_screen.load_epub(epub_path, zoom_factor=settings_data['zoom'], dpi=settings_data['dpi'])
                    self.app_instance.reader_screen.current_page = current_page
                    self.app_instance.reader_screen.show_page_numbers = settings_data['show_page_numbers']
                    self.app_instance._render_current_screen()
                
                # Update config with WiFi setting
                self.app_instance.config.set('web.always_on', settings_data['wifi_while_reading'])
                
                # Update config with sleep settings
                self.app_instance.config.set('power.sleep_timeout', settings_data['sleep_timeout'])
                self.app_instance.sleep_timeout = settings_data['sleep_timeout']
                self.app_instance.sleep_enabled = settings_data['sleep_enabled']
                # Update library screen to show current sleep status
                self.app_instance.library_screen.sleep_enabled = settings_data['sleep_enabled']

                # Update config with library settings
                self.app_instance.config.set('library.items_per_page', settings_data['items_per_page'])
                self.app_instance.library_screen.items_per_page = settings_data['items_per_page']

                # Update undervolt setting in config (requires reboot to take effect)
                old_undervolt = self.app_instance.config.get('power.undervolt', 0)
                new_undervolt = settings_data['undervolt']
                self.app_instance.config.set('power.undervolt', new_undervolt)

                # Save config changes to disk
                try:
                    self.app_instance.config.save()
                    self.logger.info("Configuration saved to disk")
                except Exception as e:
                    self.logger.error(f"Failed to save config.yaml: {e}")

                # Update /boot/firmware/config.txt if undervolt changed
                undervolt_error = None
                if old_undervolt != new_undervolt:
                    try:
                        self._apply_undervolt(new_undervolt)
                        self.logger.info(f"Undervolt changed from {old_undervolt} to {new_undervolt} - reboot required")
                    except Exception as e:
                        self.logger.error(f"Failed to apply undervolt to boot config: {e}")
                        undervolt_error = str(e)

                self.logger.info(f"Settings saved: {settings_data}")

                # Return JSON for AJAX requests, redirect for normal form submission
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.accept_json:
                    result = {'status': 'success', 'message': 'Settings saved successfully'}
                    if undervolt_error:
                        result['undervolt_warning'] = f'Settings saved but undervolt update failed: {undervolt_error}'
                    return jsonify(result)
                else:
                    return redirect(url_for('settings'))

            except Exception as e:
                self.logger.error(f"Failed to save settings: {e}")
                return jsonify({'error': str(e)}), 400

        @self.flask_app.route('/terminal/execute', methods=['POST'])
        def terminal_execute():
            """Execute a terminal command"""
            try:
                command = request.json.get('command', '').strip()
                
                if not command:
                    return jsonify({'error': 'No command provided'}), 400
                
                # Log the command
                self.logger.info(f"Terminal command: {command}")
                
                # Execute command with timeout
                import subprocess
                result = subprocess.run(
                    command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    cwd='/home/pi/PiBook'
                )
                
                # Return output
                return jsonify({
                    'stdout': result.stdout,
                    'stderr': result.stderr,
                    'returncode': result.returncode,
                    'command': command
                })
                
            except subprocess.TimeoutExpired:
                return jsonify({'error': 'Command timed out (30s limit)'}), 408
            except Exception as e:
                self.logger.error(f"Terminal command failed: {e}")
                return jsonify({'error': str(e)}), 500

        @self.flask_app.route('/api/system_stats')
        def system_stats():
            """Get comprehensive system statistics"""
            try:
                import subprocess
                import platform
                
                stats = {}
                
                # CPU Temperature
                try:
                    result = subprocess.run(['vcgencmd', 'measure_temp'], capture_output=True, text=True, timeout=2)
                    if result.returncode == 0:
                        stats['cpu_temp'] = result.stdout.strip().replace('temp=', '')
                    else:
                        stats['cpu_temp'] = 'N/A'
                except:
                    stats['cpu_temp'] = 'N/A'
                
                # CPU Voltage
                try:
                    result = subprocess.run(['vcgencmd', 'measure_volts'], capture_output=True, text=True, timeout=2)
                    if result.returncode == 0:
                        stats['cpu_voltage'] = result.stdout.strip()
                    else:
                        stats['cpu_voltage'] = 'N/A'
                except:
                    stats['cpu_voltage'] = 'N/A'
                
                # Undervolt setting from config
                stats['undervolt'] = self.app_instance.config.get('power.undervolt', 0)
                
                # Throttle status
                try:
                    result = subprocess.run(['vcgencmd', 'get_throttled'], capture_output=True, text=True, timeout=2)
                    if result.returncode == 0:
                        throttled = result.stdout.strip().replace('throttled=', '')
                        if throttled == '0x0':
                            stats['throttle_status'] = 'OK'
                            stats['throttle_detail'] = 'No throttling detected'
                        else:
                            stats['throttle_status'] = throttled
                            stats['throttle_detail'] = 'Warning: Throttling detected!'
                    else:
                        stats['throttle_status'] = 'N/A'
                        stats['throttle_detail'] = 'Unable to read'
                except:
                    stats['throttle_status'] = 'N/A'
                    stats['throttle_detail'] = 'Unable to read'
                
                # OS Information
                try:
                    with open('/etc/os-release', 'r') as f:
                        os_info = {}
                        for line in f:
                            if '=' in line:
                                key, value = line.strip().split('=', 1)
                                os_info[key] = value.strip('"')
                        stats['os_name'] = os_info.get('PRETTY_NAME', 'Linux')
                except:
                    stats['os_name'] = platform.system() + ' ' + platform.release()
                
                # System Uptime
                try:
                    with open('/proc/uptime', 'r') as f:
                        uptime_seconds = float(f.read().split()[0])
                        days = int(uptime_seconds // 86400)
                        hours = int((uptime_seconds % 86400) // 3600)
                        minutes = int((uptime_seconds % 3600) // 60)
                        if days > 0:
                            stats['uptime'] = f"{days}d {hours}h {minutes}m"
                        elif hours > 0:
                            stats['uptime'] = f"{hours}h {minutes}m"
                        else:
                            stats['uptime'] = f"{minutes}m"
                except:
                    stats['uptime'] = 'N/A'
                
                # CPU Core Information
                try:
                    # Get total CPU cores
                    with open('/sys/devices/system/cpu/present', 'r') as f:
                        present = f.read().strip()
                        # Format is usually "0-3" for 4 cores
                        if '-' in present:
                            total_cores = int(present.split('-')[1]) + 1
                        else:
                            total_cores = 1
                    
                    # Get online/active CPU cores
                    with open('/sys/devices/system/cpu/online', 'r') as f:
                        online = f.read().strip()
                        # Format can be "0-3" or "0,2-3" etc
                        active_cores = 0
                        for part in online.split(','):
                            if '-' in part:
                                start, end = part.split('-')
                                active_cores += int(end) - int(start) + 1
                            else:
                                active_cores += 1
                    
                    stats['total_cores'] = total_cores
                    stats['active_cores'] = active_cores
                except:
                    stats['total_cores'] = 'N/A'
                    stats['active_cores'] = 'N/A'
                
                # Disk Space
                try:
                    result = subprocess.run(['df', '-h', '/'], capture_output=True, text=True, timeout=2)
                    if result.returncode == 0:
                        lines = result.stdout.strip().split('\n')
                        if len(lines) > 1:
                            parts = lines[1].split()
                            if len(parts) >= 4:
                                stats['disk_total'] = parts[1]
                                stats['disk_used'] = parts[2]
                                stats['disk_free'] = parts[3]
                                stats['disk_percent'] = parts[4] if len(parts) > 4 else 'N/A'
                except:
                    stats['disk_free'] = 'N/A'
                
                # Memory Usage
                try:
                    result = subprocess.run(['free', '-h'], capture_output=True, text=True, timeout=2)
                    if result.returncode == 0:
                        lines = result.stdout.strip().split('\n')
                        if len(lines) > 1:
                            parts = lines[1].split()
                            if len(parts) >= 3:
                                stats['memory_total'] = parts[1]
                                stats['memory_used'] = parts[2]
                                stats['memory_free'] = parts[3] if len(parts) > 3 else 'N/A'
                                # Calculate percentage
                                try:
                                    total = float(parts[1].replace('Gi', '').replace('Mi', ''))
                                    used = float(parts[2].replace('Gi', '').replace('Mi', ''))
                                    percent = int((used / total) * 100) if total > 0 else 0
                                    stats['memory_percent'] = f"{percent}%"
                                except:
                                    stats['memory_percent'] = 'N/A'
                except:
                    stats['memory_used'] = 'N/A'
                    stats['memory_total'] = 'N/A'
                
                return jsonify(stats)
                
            except Exception as e:
                self.logger.error(f"Failed to get system stats: {e}")
                return jsonify({'error': str(e)}), 500

    def _get_books(self):
        """Get list of EPUB files"""
        books = []
        if os.path.exists(self.books_dir):
            for filename in sorted(os.listdir(self.books_dir)):
                if filename.lower().endswith('.epub'):
                    filepath = os.path.join(self.books_dir, filename)
                    size = os.path.getsize(filepath) / (1024 * 1024)  # MB
                    books.append({
                        'filename': filename,
                        'size': f"{size:.2f} MB"
                    })
        return books

    def _load_todos(self):
        """Load to-do tasks from todos.json"""
        todos_file = 'todos.json'
        if os.path.exists(todos_file):
            try:
                with open(todos_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.error(f"Error loading todos: {e}")
                return {'tasks': []}
        return {'tasks': []}

    def _save_todos(self, todos):
        """Save to-do tasks to todos.json"""
        todos_file = 'todos.json'
        try:
            with open(todos_file, 'w') as f:
                json.dump(todos, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error saving todos: {e}")
            raise

    def _refresh_todo_screen(self):
        """Refresh To-Do screen on e-ink display with partial refresh"""
        try:
            from src.ui.navigation import Screen
            # Only refresh if currently on To-Do screen
            if self.app_instance.navigation.is_on_screen(Screen.TODO):
                self.app_instance._render_current_screen(force_partial=True)
                self.logger.debug("Refreshed To-Do screen (partial)")
        except Exception as e:
            self.logger.error(f"Failed to refresh To-Do screen: {e}")

    def _load_settings(self, settings_file: str) -> dict:
        """Load settings from file, with defaults from config.yaml"""
        # Start with defaults from config.yaml
        default_settings = {
            'zoom': 1.0,
            'dpi': 150,
            'full_refresh_interval': self.app_instance.config.get('display.full_refresh_interval', 10),
            'show_page_numbers': True,
            'wifi_while_reading': self.app_instance.config.get('web.always_on', False),
            'sleep_enabled': True,
            'sleep_message': 'Shh I\'m sleeping',
            'sleep_timeout': self.app_instance.config.get('power.sleep_timeout', 120),
            'items_per_page': self.app_instance.config.get('library.items_per_page', 4),
            'undervolt': self.app_instance.config.get('power.undervolt', -2)
        }

        # Override with saved settings if they exist
        if os.path.exists(settings_file):
            try:
                with open(settings_file, 'r') as f:
                    saved_settings = json.load(f)
                    default_settings.update(saved_settings)
                    self.logger.info(f"Loaded settings from {settings_file}")
            except Exception as e:
                self.logger.error(f"Error loading settings: {e}")

        return default_settings

    def _save_settings(self, settings_data):
        """Save settings to settings.json"""
        settings_file = 'settings.json'
        try:
            with open(settings_file, 'w') as f:
                json.dump(settings_data, indent=2, fp=f)
        except Exception as e:
            self.logger.error(f"Failed to save settings: {e}")
            raise

    def _apply_undervolt(self, undervolt_value):
        """Apply undervolt setting to /boot/firmware/config.txt using sudo helper script"""
        try:
            import subprocess
            script_path = '/home/pi/PiBook/scripts/apply_undervolt.sh'

            # Use sudo to run the helper script
            result = subprocess.run(
                ['sudo', script_path, str(undervolt_value)],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                self.logger.info(f"Successfully applied undervolt={undervolt_value} via helper script")
                self.logger.info(result.stdout.strip())
            else:
                self.logger.error(f"Failed to apply undervolt: {result.stderr}")
                raise Exception(f"Helper script failed: {result.stderr}")

        except subprocess.TimeoutExpired:
            self.logger.error("Timeout applying undervolt setting")
            raise
        except Exception as e:
            self.logger.error(f"Failed to apply undervolt: {e}")
            raise

    def run(self):
        """Start the web server in a separate thread"""
        import threading
        thread = threading.Thread(target=self._run_server, daemon=True)
        thread.start()
        self.logger.info(f"Web server started on port {self.port}")

    def _run_server(self):
        """Internal method to run Flask server"""
        self.flask_app.run(host='0.0.0.0', port=self.port, debug=False, use_reloader=False)

