"""
Flask web server for PiBook remote control and file management.
Provides web interface for:
- Uploading/managing EPUB files
- Remote navigation (next/prev/select buttons)
- Book selection
"""

from flask import Flask, render_template_string, request, jsonify, send_from_directory, redirect, url_for
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
        self.flask_app = Flask(__name__)
        self.flask_app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max file size

        self._setup_routes()

    def _setup_routes(self):
        """Setup Flask routes"""

        @self.flask_app.route('/')
        def index():
            """Main page with file manager and controls"""
            settings_data = self._load_settings('settings.json')
            return render_template_string(HTML_TEMPLATE, books=self._get_books(), settings=settings_data)

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


# HTML Template for the web interface
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>PiBook Manager</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { box-sizing: border-box; }
        body {
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 0;
            background: #f5f5f5;
        }
        .container {
            max-width: 900px;
            margin: 0 auto;
        }
        h1 {
            color: #333;
            margin: 0;
            padding: 20px;
            background: white;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .tabs {
            display: flex;
            background: white;
            border-bottom: 2px solid #4CAF50;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            position: sticky;
            top: 0;
            z-index: 100;
        }
        .tab {
            flex: 1;
            padding: 15px 20px;
            text-align: center;
            background: #f0f0f0;
            border: none;
            cursor: pointer;
            font-size: 16px;
            font-weight: bold;
            color: #666;
            transition: all 0.3s;
        }
        .tab:hover {
            background: #e0e0e0;
        }
        .tab.active {
            background: white;
            color: #4CAF50;
            border-bottom: 3px solid #4CAF50;
            margin-bottom: -2px;
        }
        .tab-content {
            display: none;
            padding: 20px;
        }
        .tab-content.active {
            display: block;
        }
        .section {
            background: white;
            padding: 20px;
            margin: 20px 0;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        h2 {
            color: #333;
            margin-top: 0;
        }
        .controls {
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            gap: 10px;
            margin-top: 10px;
        }
        .btn {
            padding: 15px;
            font-size: 16px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            background: #4CAF50;
            color: white;
            transition: background 0.3s;
        }
        .btn:active {
            background: #45a049;
        }
        .btn-secondary {
            background: #008CBA;
        }
        .btn-danger {
            background: #f44336;
        }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th, td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }
        th {
            background: #4CAF50;
            color: white;
        }
        .upload-form {
            display: flex;
            gap: 10px;
            align-items: center;
        }
        input[type="file"] {
            flex: 1;
            padding: 10px;
        }
        .empty {
            text-align: center;
            color: #999;
            padding: 40px;
        }
        .form-group {
            margin: 15px 0;
        }
        label {
            display: block;
            font-weight: bold;
            margin-bottom: 5px;
            color: #333;
        }
        input[type="number"], input[type="text"] {
            width: 100%;
            padding: 10px;
            font-size: 16px;
            border: 1px solid #ddd;
            border-radius: 5px;
            box-sizing: border-box;
        }
        .checkbox-group {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .checkbox-group input[type="checkbox"] {
            width: 20px;
            height: 20px;
        }
        .help-text {
            font-size: 12px;
            color: #666;
            margin-top: 5px;
        }
        h3 {
            color: #555;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📚 PiBook Manager</h1>

        <div class="tabs">
            <button class="tab active" onclick="switchTab(event, 'library')">📖 Library</button>
            <button class="tab" onclick="switchTab(event, 'settings')">⚙️ Settings</button>
            <button class="tab" onclick="switchTab(event, 'navigation')">🧭 Navigation</button>
            <button class="tab" onclick="switchTab(event, 'terminal')">💻 Terminal</button>
        </div>

        <!-- Library Tab -->
        <div id="library" class="tab-content active">
            <!-- File Upload -->
            <div class="section">
                <h2>📤 Upload EPUB Books</h2>
                <form action="/upload" method="post" enctype="multipart/form-data" class="upload-form">
                    <input type="file" name="file" accept=".epub" multiple required>
                    <button type="submit" class="btn">Upload</button>
                </form>
                <p style="color: #666; font-size: 14px; margin-top: 10px;">
                    💡 Tip: Hold Ctrl (Windows/Linux) or Cmd (Mac) to select multiple files
                </p>
            </div>

            <!-- Book List -->
            <div class="section">
                <h2>📖 Library ({{ books|length }} books)</h2>
                {% if books %}
                <table>
                    <tr>
                        <th>Filename</th>
                        <th>Size</th>
                        <th>Actions</th>
                    </tr>
                    {% for book in books %}
                    <tr>
                        <td>{{ book.filename }}</td>
                        <td>{{ book.size }}</td>
                        <td>
                            <a href="/delete/{{ book.filename }}"
                               onclick="return confirm('Delete {{ book.filename }}?')"
                               class="btn btn-danger"
                               style="padding: 5px 10px; text-decoration: none; font-size: 12px;">
                                Delete
                            </a>
                        </td>
                    </tr>
                    {% endfor %}
                </table>
                {% else %}
                <div class="empty">
                    <p>No books yet. Upload an EPUB to get started!</p>
                </div>
                {% endif %}
            </div>
        </div>

        <!-- Settings Tab -->
        <div id="settings" class="tab-content">
            <div class="section">
                <h2>⚙️ PiBook Settings</h2>
                <form action="/save_settings" method="post">
                    <h3 style="margin-top: 20px; color: #555; border-bottom: 2px solid #4CAF50; padding-bottom: 10px;">📖 Reading Settings</h3>

                    <div class="form-group">
                        <label for="zoom">Zoom Level</label>
                        <input type="number" id="zoom" name="zoom"
                               value="{{ settings.zoom }}" min="0.5" max="2.0" step="0.1">
                        <p class="help-text">Text size (0.5-2.0). 1.0 = fit to screen, less than 1.0 = smaller, greater than 1.0 = larger</p>
                    </div>

                    <div class="form-group">
                        <label for="dpi">DPI (Rendering Quality)</label>
                        <input type="number" id="dpi" name="dpi"
                               value="{{ settings.dpi }}" min="72" max="300" step="1">
                        <p class="help-text">Rendering resolution (72-300). Higher = sharper text but slower. Default: 150</p>
                    </div>

                    <div class="form-group">
                        <label for="full_refresh_interval">Full Refresh Interval</label>
                        <input type="number" id="full_refresh_interval" name="full_refresh_interval"
                               value="{{ settings.full_refresh_interval }}" min="1" max="20" step="1">
                        <p class="help-text">Number of page turns before full refresh to clear ghosting (1-20)</p>
                    </div>

                    <div class="form-group">
                        <div class="checkbox-group">
                            <input type="checkbox" id="show_page_numbers" name="show_page_numbers"
                                   {% if settings.show_page_numbers %}checked{% endif %}>
                            <label for="show_page_numbers" style="margin: 0;">Show Page Numbers</label>
                        </div>
                        <p class="help-text">Display "Page X of Y" at bottom of screen when reading</p>
                    </div>

                    <div class="form-group">
                        <label for="items_per_page">Books Per Page</label>
                        <input type="number" id="items_per_page" name="items_per_page"
                               value="{{ settings.items_per_page }}" min="3" max="6" step="1">
                        <p class="help-text">Number of books shown on library screen (3-6)</p>
                    </div>

                    <div class="form-group">
                        <div class="checkbox-group">
                            <input type="checkbox" id="wifi_while_reading" name="wifi_while_reading"
                                   {% if settings.wifi_while_reading %}checked{% endif %}>
                            <label for="wifi_while_reading" style="margin: 0;">Keep WiFi On While Reading</label>
                        </div>
                        <p class="help-text">🔋 Uncheck to save battery (WiFi turns off when reading, on when in library)</p>
                    </div>

                    <h3 style="margin-top: 30px; color: #555; border-bottom: 2px solid #4CAF50; padding-bottom: 10px;">🔋 Power Management</h3>

                    <div class="form-group">
                        <div class="checkbox-group">
                            <input type="checkbox" id="sleep_enabled" name="sleep_enabled"
                                   {% if settings.sleep_enabled %}checked{% endif %}>
                            <label for="sleep_enabled" style="margin: 0;">Enable Sleep Mode</label>
                        </div>
                        <p class="help-text">🔋 When enabled, device sleeps after inactivity to save battery</p>
                    </div>

                    <div class="form-group">
                        <label for="sleep_timeout">Sleep Timeout (seconds)</label>
                        <input type="number" id="sleep_timeout" name="sleep_timeout"
                               value="{{ settings.sleep_timeout }}" min="30" max="600" step="30">
                        <p class="help-text">Time of inactivity before sleep (30-600 seconds). Lower = better battery</p>
                    </div>

                    <div class="form-group">
                        <label for="sleep_message">Sleep Screen Message</label>
                        <input type="text" id="sleep_message" name="sleep_message"
                               value="{{ settings.sleep_message }}" maxlength="50"
                               style="width: 100%; padding: 10px; font-size: 16px; border: 1px solid #ddd; border-radius: 5px;">
                        <p class="help-text">Message displayed when device goes to sleep (max 50 characters)</p>
                    </div>

                    <h3 style="margin-top: 30px; color: #555; border-bottom: 2px solid #FF9800; padding-bottom: 10px;">⚡ CPU Undervolting (Experimental)</h3>

                    <div class="form-group">
                        <label for="undervolt">Undervolt Level</label>
                        <input type="number" id="undervolt" name="undervolt"
                               value="{{ settings.undervolt }}" min="-8" max="0" step="1">
                        <p class="help-text">CPU voltage reduction: 0 = none, -2 = 50mV (safe), -4 = 100mV, -6 = 150mV, -8 = 200mV (max)</p>
                        <p class="help-text" style="color: #d32f2f; font-weight: bold;">⚠️ WARNING: Values below -4 may cause instability. Requires reboot to apply.</p>
                        <p class="help-text" id="voltage-status" style="color: #1976d2; font-weight: bold;">Current CPU Voltage: Loading...</p>
                    </div>

                    <button type="submit" class="btn">Save Settings</button>
                </form>

                <div id="settings-message" style="margin-top: 15px; padding: 15px; border-radius: 8px; display: none;">
                    <!-- Success/error messages will appear here -->
                </div>

                <div style="margin-top: 20px; padding: 15px; background: #fff3cd; border-radius: 8px; border-left: 4px solid #ff9800;">
                    <p style="margin: 0 0 10px 0; font-weight: bold; color: #856404;">💡 Undervolt changes require reboot</p>
                    <button class="btn" style="background: #ff9800; margin-top: 0;" onclick="if(confirm('Reboot PiBook now? This will close all connections.')) { fetch('/reboot').then(() => alert('Rebooting... Wait 30 seconds then reconnect.')); }">Reboot PiBook</button>
                </div>
            </div>
        </div>

        <!-- Navigation Tab -->
        <div id="navigation" class="tab-content">
            <!-- Remote Control -->
            <div class="section">
                <h2>🎮 Remote Control</h2>
                <p style="color: #666; margin-bottom: 15px;">Control your PiBook e-reader remotely</p>
                <div class="controls">
                    <button class="btn" onclick="control('prev')">◀ Previous</button>
                    <button class="btn btn-secondary" onclick="control('select')">✓ Select</button>
                    <button class="btn" onclick="control('next')">Next ▶</button>
                </div>
                <div class="controls" style="margin-top: 10px;">
                    <button class="btn btn-secondary" onclick="control('back')">← Back</button>
                    <button class="btn btn-secondary" onclick="control('menu')">≡ Menu</button>
                    <button class="btn" onclick="location.reload()">🔄 Refresh</button>
                </div>
            </div>

            <!-- System Stats -->
            <div class="section" style="margin-top: 30px;">
                <h2>📊 System Information</h2>
                <p style="color: #666; margin-bottom: 15px;">Real-time system statistics</p>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 15px;">
                    <div style="padding: 15px; background: #f9f9f9; border-radius: 5px; border-left: 4px solid #4CAF50;">
                        <div style="font-size: 12px; color: #666; margin-bottom: 5px;">CPU Temperature</div>
                        <div id="cpu-temp" style="font-size: 24px; font-weight: bold; color: #333;">Loading...</div>
                    </div>
                    <div style="padding: 15px; background: #f9f9f9; border-radius: 5px; border-left: 4px solid #2196F3;">
                        <div style="font-size: 12px; color: #666; margin-bottom: 5px;">CPU Voltage</div>
                        <div id="cpu-voltage" style="font-size: 24px; font-weight: bold; color: #333;">Loading...</div>
                    </div>
                    <div style="padding: 15px; background: #f9f9f9; border-radius: 5px; border-left: 4px solid #FF9800;">
                        <div style="font-size: 12px; color: #666; margin-bottom: 5px;">Undervolt Setting</div>
                        <div id="undervolt-setting" style="font-size: 24px; font-weight: bold; color: #333;">Loading...</div>
                    </div>
                    <div style="padding: 15px; background: #f9f9f9; border-radius: 5px; border-left: 4px solid #9C27B0;">
                        <div style="font-size: 12px; color: #666; margin-bottom: 5px;">Throttle Status</div>
                        <div id="throttle-status" style="font-size: 24px; font-weight: bold; color: #333;">Loading...</div>
                    </div>
                    <div style="padding: 15px; background: #f9f9f9; border-radius: 5px; border-left: 4px solid #00BCD4;">
                        <div style="font-size: 12px; color: #666; margin-bottom: 5px;">Operating System</div>
                        <div id="os-info" style="font-size: 18px; font-weight: bold; color: #333;">Loading...</div>
                    </div>
                    <div style="padding: 15px; background: #f9f9f9; border-radius: 5px; border-left: 4px solid #607D8B;">
                        <div style="font-size: 12px; color: #666; margin-bottom: 5px;">System Uptime</div>
                        <div id="uptime" style="font-size: 18px; font-weight: bold; color: #333;">Loading...</div>
                    </div>
                    <div style="padding: 15px; background: #f9f9f9; border-radius: 5px; border-left: 4px solid #3F51B5;">
                        <div style="font-size: 12px; color: #666; margin-bottom: 5px;">Active CPU Cores</div>
                        <div id="cpu-cores" style="font-size: 24px; font-weight: bold; color: #333;">Loading...</div>
                    </div>
                </div>
                <button class="btn" onclick="refreshSystemStats()" style="margin-top: 15px; width: 100%;">🔄 Refresh Stats</button>
            </div>

            <!-- External Links -->
            <div class="section" style="margin-top: 30px;">
                <h2>🔗 External Links</h2>
                <p style="color: #666; margin-bottom: 15px;">Access related services</p>
                <div class="controls">
                    <button class="btn" onclick="window.open('http://' + window.location.hostname + ':8421', '_blank')" style="background: #9C27B0;">🔋 PiSugar Battery Manager</button>
                </div>
                <p class="help-text" style="margin-top: 10px;">Opens PiSugar web interface for advanced battery management and configuration</p>
            </div>
        </div>

        <!-- Terminal Tab -->
        <div id="terminal" class="tab-content">
            <div class="section">
                <h2>💻 Terminal</h2>
                <p style="color: #666; margin-bottom: 15px;">Execute shell commands on your PiBook</p>
                
                <div style="margin-bottom: 15px;">
                    <label style="font-weight: bold; margin-bottom: 5px; display: block;">Quick Commands:</label>
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 10px;">
                        <button class="btn btn-secondary" onclick="setCommand('git status')" style="padding: 8px; font-size: 14px;">git status</button>
                        <button class="btn btn-secondary" onclick="setCommand('git pull')" style="padding: 8px; font-size: 14px;">git pull</button>
                        <button class="btn btn-secondary" onclick="setCommand('ls -la')" style="padding: 8px; font-size: 14px;">ls -la</button>
                        <button class="btn btn-secondary" onclick="setCommand('df -h')" style="padding: 8px; font-size: 14px;">df -h (disk space)</button>
                        <button class="btn btn-secondary" onclick="setCommand('free -h')" style="padding: 8px; font-size: 14px;">free -h (memory)</button>
                        <button class="btn btn-secondary" onclick="setCommand('sudo systemctl restart pibook')" style="padding: 8px; font-size: 14px;">restart pibook</button>
                    </div>
                </div>

                <div style="margin-bottom: 15px;">
                    <label style="font-weight: bold; margin-bottom: 5px; display: block;">Output:</label>
                    <div id="terminal-output" style="background: #1e1e1e; color: #d4d4d4; padding: 15px; border-radius: 5px; font-family: 'Courier New', monospace; font-size: 13px; min-height: 400px; max-height: 600px; overflow-y: auto; white-space: pre-wrap; word-wrap: break-word;"><span style="color: #4CAF50;">Welcome to PiBook Terminal</span>
<span style="color: #888;">Type a command below and click Execute, or use Quick Commands</span>
</div>
                    <div style="margin-top: 10px; display: flex; gap: 10px;">
                        <button class="btn btn-secondary" onclick="clearTerminal()" style="flex: 1;">Clear Output</button>
                        <button class="btn btn-secondary" onclick="copyOutput()" style="flex: 1;">Copy Output</button>
                    </div>
                </div>

                <div>
                    <label for="terminal-input" style="font-weight: bold; margin-bottom: 5px; display: block;">Command:</label>
                    <div style="display: flex; gap: 10px;">
                        <input type="text" id="terminal-input" placeholder="Enter command (e.g., ls -la, git status, pwd)" 
                               style="flex: 1; padding: 10px; font-family: 'Courier New', monospace; font-size: 14px; border: 1px solid #ddd; border-radius: 5px;">
                        <button class="btn" onclick="executeCommand()" style="width: 120px;">Execute</button>
                    </div>
                    <p class="help-text">⚠️ Commands run in /home/pi/PiBook directory with 30s timeout</p>
                </div>
            </div>
        </div>
    </div>

    <script>
        function switchTab(event, tabName) {
            // Hide all tab content
            const tabContents = document.getElementsByClassName('tab-content');
            for (let content of tabContents) {
                content.classList.remove('active');
            }

            // Remove active class from all tabs
            const tabs = document.getElementsByClassName('tab');
            for (let tab of tabs) {
                tab.classList.remove('active');
            }

            // Show selected tab and mark button as active
            document.getElementById(tabName).classList.add('active');
            event.currentTarget.classList.add('active');
        }

        function control(action) {
            fetch('/control/' + action)
                .then(response => response.json())
                .then(data => {
                    console.log('Action:', action, 'Status:', data.status);
                })
                .catch(error => console.error('Error:', error));
        }

        // Handle settings form submission
        document.addEventListener('DOMContentLoaded', function() {
            const settingsForm = document.querySelector('form[action="/save_settings"]');
            if (settingsForm) {
                settingsForm.addEventListener('submit', function(e) {
                    e.preventDefault();

                    const formData = new FormData(settingsForm);
                    const messageDiv = document.getElementById('settings-message');

                    fetch('/save_settings', {
                        method: 'POST',
                        body: formData
                    })
                    .then(response => {
                        if (response.redirected || response.ok) {
                            // Show success message
                            messageDiv.style.display = 'block';
                            messageDiv.style.background = '#d4edda';
                            messageDiv.style.borderLeft = '4px solid #28a745';
                            messageDiv.style.color = '#155724';
                            messageDiv.innerHTML = '<strong>✅ Settings saved successfully!</strong><br>Changes have been applied. If you changed the undervolt setting, click "Reboot PiBook" below to apply.';

                            // Scroll to message
                            messageDiv.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

                            // Reload voltage status
                            setTimeout(() => {
                                fetch('/api/cpu_voltage')
                                    .then(r => r.json())
                                    .then(data => {
                                        const statusEl = document.getElementById('voltage-status');
                                        if (statusEl && data.voltage) {
                                            statusEl.textContent = 'Current CPU Voltage: ' + data.voltage + ' (Undervolt: ' + data.undervolt_setting + ')';
                                        }
                                    });
                            }, 500);
                        } else {
                            throw new Error('Save failed');
                        }
                    })
                    .catch(error => {
                        // Show error message
                        messageDiv.style.display = 'block';
                        messageDiv.style.background = '#f8d7da';
                        messageDiv.style.borderLeft = '4px solid #dc3545';
                        messageDiv.style.color = '#721c24';
                        messageDiv.innerHTML = '<strong>❌ Error saving settings!</strong><br>' + error.message;
                        messageDiv.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                    });
                });
            }
        });

        // Load current CPU voltage when page loads
        fetch('/api/cpu_voltage')
            .then(response => response.json())
            .then(data => {
                const statusEl = document.getElementById('voltage-status');
                if (statusEl && data.voltage) {
                    statusEl.textContent = 'Current CPU Voltage: ' + data.voltage + ' (Undervolt: ' + data.undervolt_setting + ')';
                } else if (statusEl) {
                    statusEl.textContent = 'Current CPU Voltage: Unable to read';
                }
            })
            .catch(err => {
                const statusEl = document.getElementById('voltage-status');
                if (statusEl) {
                    statusEl.textContent = 'Current CPU Voltage: Error loading';
                }
            });

        // Terminal functions
        function setCommand(cmd) {
            document.getElementById('terminal-input').value = cmd;
        }

        function executeCommand() {
            const input = document.getElementById('terminal-input');
            const output = document.getElementById('terminal-output');
            const command = input.value.trim();

            if (!command) {
                return;
            }

            // Add command to output
            appendToTerminal(`<span style="color: #4CAF50;">$ ${escapeHtml(command)}</span>`);

            // Execute command
            fetch('/terminal/execute', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ command: command })
            })
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    appendToTerminal(`<span style="color: #f44336;">Error: ${escapeHtml(data.error)}</span>`);
                } else {
                    // Show stdout
                    if (data.stdout) {
                        appendToTerminal(escapeHtml(data.stdout));
                    }
                    // Show stderr in red
                    if (data.stderr) {
                        appendToTerminal(`<span style="color: #ff9800;">${escapeHtml(data.stderr)}</span>`);
                    }
                    // Show return code if non-zero
                    if (data.returncode !== 0) {
                        appendToTerminal(`<span style="color: #f44336;">Exit code: ${data.returncode}</span>`);
                    }
                }
                appendToTerminal(''); // Empty line for spacing
            })
            .catch(error => {
                appendToTerminal(`<span style="color: #f44336;">Network error: ${escapeHtml(error.message)}</span>`);
            });

            // Clear input
            input.value = '';
        }

        function appendToTerminal(text) {
            const output = document.getElementById('terminal-output');
            output.innerHTML += text + '<br>';
            // Auto-scroll to bottom
            output.scrollTop = output.scrollHeight;
        }

        function clearTerminal() {
            const output = document.getElementById('terminal-output');
            output.innerHTML = '<span style="color: #4CAF50;">Welcome to PiBook Terminal</span><br><span style="color: #888;">Type a command above and click Execute, or use Quick Commands</span><br>';
        }

        function copyOutput() {
            const output = document.getElementById('terminal-output');
            const text = output.innerText;
            navigator.clipboard.writeText(text).then(() => {
                alert('Output copied to clipboard!');
            }).catch(err => {
                alert('Failed to copy: ' + err);
            });
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }

        // Allow Enter key to execute command
        document.addEventListener('DOMContentLoaded', function() {
            const terminalInput = document.getElementById('terminal-input');
            if (terminalInput) {
                terminalInput.addEventListener('keypress', function(e) {
                    if (e.key === 'Enter') {
                        executeCommand();
                    }
                });
            }
            
            // Load system stats when page loads
            refreshSystemStats();
        });

        // System stats functions
        function refreshSystemStats() {
            fetch('/api/system_stats')
                .then(response => response.json())
                .then(data => {
                    // Update CPU Temperature
                    const tempEl = document.getElementById('cpu-temp');
                    if (tempEl && data.cpu_temp) {
                        tempEl.textContent = data.cpu_temp;
                        // Color code based on temperature
                        const temp = parseFloat(data.cpu_temp);
                        if (temp > 70) {
                            tempEl.style.color = '#f44336'; // Red
                        } else if (temp > 60) {
                            tempEl.style.color = '#ff9800'; // Orange
                        } else {
                            tempEl.style.color = '#4CAF50'; // Green
                        }
                    }
                    
                    // Update CPU Voltage
                    const voltEl = document.getElementById('cpu-voltage');
                    if (voltEl && data.cpu_voltage) {
                        voltEl.textContent = data.cpu_voltage;
                    }
                    
                    // Update Undervolt Setting
                    const undervoltEl = document.getElementById('undervolt-setting');
                    if (undervoltEl) {
                        const mv = Math.abs(data.undervolt) * 25;
                        undervoltEl.textContent = `${data.undervolt} (-${mv}mV)`;
                    }
                    
                    // Update Throttle Status
                    const throttleEl = document.getElementById('throttle-status');
                    if (throttleEl && data.throttle_status) {
                        throttleEl.textContent = data.throttle_status;
                        if (data.throttle_status === 'OK') {
                            throttleEl.style.color = '#4CAF50'; // Green
                        } else {
                            throttleEl.style.color = '#f44336'; // Red
                        }
                        throttleEl.title = data.throttle_detail || '';
                    }
                    
                    // Update OS Info
                    const osEl = document.getElementById('os-info');
                    if (osEl && data.os_name) {
                        osEl.textContent = data.os_name;
                    }
                    
                    // Update Uptime
                    const uptimeEl = document.getElementById('uptime');
                    if (uptimeEl && data.uptime) {
                        uptimeEl.textContent = data.uptime;
                    }
                    
                    // Update CPU Cores
                    const coresEl = document.getElementById('cpu-cores');
                    if (coresEl && data.active_cores && data.total_cores) {
                        coresEl.textContent = `${data.active_cores}/${data.total_cores}`;
                        // Color code: green if 1 core (power saving), blue if multiple
                        if (data.active_cores === 1) {
                            coresEl.style.color = '#4CAF50'; // Green - power saving mode
                        } else {
                            coresEl.style.color = '#2196F3'; // Blue - normal mode
                        }
                    }
                })
                .catch(error => {
                    console.error('Failed to load system stats:', error);
                });
        }

        // Refresh stats when switching to navigation tab
        const originalSwitchTab = switchTab;
        switchTab = function(event, tabName) {
            originalSwitchTab(event, tabName);
            if (tabName === 'navigation') {
                refreshSystemStats();
            }
        };
    </script>
</body>
</html>
'''

# Settings template
SETTINGS_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>PiBook Settings</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }
        h1 {
            color: #333;
        }
        .section {
            background: white;
            padding: 20px;
            margin: 20px 0;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .form-group {
            margin: 15px 0;
        }
        label {
            display: block;
            font-weight: bold;
            margin-bottom: 5px;
            color: #333;
        }
        input[type="number"] {
            width: 100%;
            padding: 10px;
            font-size: 16px;
            border: 1px solid #ddd;
            border-radius: 5px;
            box-sizing: border-box;
        }
        .checkbox-group {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .checkbox-group input[type="checkbox"] {
            width: 20px;
            height: 20px;
        }
        .btn {
            padding: 15px 30px;
            font-size: 16px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            background: #4CAF50;
            color: white;
            transition: background 0.3s;
            width: 100%;
            margin-top: 10px;
        }
        .btn:active {
            background: #45a049;
        }
        .btn-secondary {
            background: #008CBA;
        }
        .help-text {
            font-size: 12px;
            color: #666;
            margin-top: 5px;
        }
    </style>
</head>
<body>
    <h1>⚙️ PiBook Settings</h1>

    <div class="section">
        <form action="/save_settings" method="post">
            <div class="form-group">
                <label for="zoom">Zoom Level</label>
                <input type="number" id="zoom" name="zoom"
                       value="{{ settings.zoom }}" min="0.5" max="2.0" step="0.1">
                <p class="help-text">Text size (0.5-2.0). 1.0 = fit to screen, less than 1.0 = smaller, greater than 1.0 = larger</p>
            </div>

            <div class="form-group">
                <label for="dpi">DPI (Rendering Quality)</label>
                <input type="number" id="dpi" name="dpi"
                       value="{{ settings.dpi }}" min="72" max="300" step="1">
                <p class="help-text">Rendering resolution (72-300). Higher = sharper text but slower. Default: 150</p>
            </div>

            <div class="form-group">
                <label for="full_refresh_interval">Full Refresh Interval</label>
                <input type="number" id="full_refresh_interval" name="full_refresh_interval"
                       value="{{ settings.full_refresh_interval }}" min="1" max="20" step="1">
                <p class="help-text">Number of page turns before full refresh to clear ghosting (1-20)</p>
            </div>

            <div class="form-group">
                <div class="checkbox-group">
                    <input type="checkbox" id="show_page_numbers" name="show_page_numbers"
                           {% if settings.show_page_numbers %}checked{% endif %}>
                    <label for="show_page_numbers" style="margin: 0;">Show Page Numbers</label>
                </div>
                <p class="help-text">Display "Page X of Y" at bottom of screen when reading</p>
            </div>

            <div class="form-group">
                <div class="checkbox-group">
                    <input type="checkbox" id="wifi_while_reading" name="wifi_while_reading"
                           {% if settings.wifi_while_reading %}checked{% endif %}>
                    <label for="wifi_while_reading" style="margin: 0;">Keep WiFi On While Reading</label>
                </div>
                <p class="help-text">🔋 Uncheck to save battery (WiFi turns off when reading, on when in library)</p>
            </div>

            <h3 style="margin-top: 30px; color: #555; border-bottom: 2px solid #4CAF50; padding-bottom: 10px;">🔋 Power Management</h3>

            <div class="form-group">
                <div class="checkbox-group">
                    <input type="checkbox" id="sleep_enabled" name="sleep_enabled"
                           {% if settings.sleep_enabled %}checked{% endif %}>
                    <label for="sleep_enabled" style="margin: 0;">Enable Sleep Mode</label>
                </div>
                <p class="help-text">🔋 When enabled, device sleeps after inactivity to save battery</p>
            </div>

            <div class="form-group">
                <label for="sleep_timeout">Sleep Timeout (seconds)</label>
                <input type="number" id="sleep_timeout" name="sleep_timeout"
                       value="{{ settings.sleep_timeout }}" min="30" max="600" step="30">
                <p class="help-text">Time of inactivity before sleep (30-600 seconds). Lower = better battery</p>
            </div>

            <div class="form-group">
                <label for="sleep_message">Sleep Screen Message</label>
                <input type="text" id="sleep_message" name="sleep_message"
                       value="{{ settings.sleep_message }}" maxlength="50"
                       style="width: 100%; padding: 10px; font-size: 16px; border: 1px solid #ddd; border-radius: 5px;">
                <p class="help-text">Message displayed when device goes to sleep (max 50 characters)</p>
            </div>

            <h3 style="margin-top: 30px; color: #555; border-bottom: 2px solid #FF9800; padding-bottom: 10px;">⚡ CPU Undervolting (Experimental)</h3>

            <div class="form-group">
                <label for="undervolt">Undervolt Level</label>
                <input type="number" id="undervolt" name="undervolt"
                       value="{{ settings.undervolt }}" min="-8" max="0" step="1">
                <p class="help-text">CPU voltage reduction: 0 = none, -2 = 50mV (safe), -4 = 100mV, -6 = 150mV, -8 = 200mV (max)</p>
                <p class="help-text" style="color: #d32f2f; font-weight: bold;">⚠️ WARNING: Values below -4 may cause instability. Requires reboot to apply.</p>
                <p class="help-text" id="voltage-status" style="color: #1976d2; font-weight: bold;">Current CPU Voltage: Loading...</p>
            </div>

            <div class="form-group">
                <label for="items_per_page">Books Per Page</label>
                <input type="number" id="items_per_page" name="items_per_page"
                       value="{{ settings.items_per_page }}" min="3" max="6" step="1">
                <p class="help-text">Number of books shown on library screen (3-6)</p>
            </div>

            <button type="submit" class="btn">Save Settings</button>
        </form>

        <button class="btn btn-secondary" onclick="window.location.href='/'">Back to Library</button>

        <div style="margin-top: 20px; padding: 15px; background: #fff3cd; border-radius: 8px; border-left: 4px solid #ff9800;">
            <p style="margin: 0 0 10px 0; font-weight: bold; color: #856404;">💡 Undervolt changes require reboot</p>
            <button class="btn" style="background: #ff9800; margin-top: 0;" onclick="if(confirm('Reboot PiBook now? This will close all connections.')) { fetch('/reboot').then(() => alert('Rebooting... Wait 30 seconds then reconnect.')); }">Reboot PiBook</button>
        </div>
    </div>

    <script>
        // Load current CPU voltage
        fetch('/api/cpu_voltage')
            .then(response => response.json())
            .then(data => {
                const statusEl = document.getElementById('voltage-status');
                if (data.voltage) {
                    statusEl.textContent = 'Current CPU Voltage: ' + data.voltage + ' (Undervolt: ' + data.undervolt_setting + ')';
                } else {
                    statusEl.textContent = 'Current CPU Voltage: Unable to read';
                }
            })
            .catch(err => {
                document.getElementById('voltage-status').textContent = 'Current CPU Voltage: Error loading';
            });
    </script>
</body>
</html>
'''
