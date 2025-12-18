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
            return render_template_string(HTML_TEMPLATE, books=self._get_books())

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

        @self.flask_app.route('/settings')
        def settings():
            """Settings page"""
            settings_data = self._load_settings()
            return render_template_string(SETTINGS_TEMPLATE, settings=settings_data)

        @self.flask_app.route('/save_settings', methods=['POST'])
        def save_settings():
            """Save user settings"""
            try:
                settings_data = {
                    'font_size': int(request.form.get('font_size', 12)),
                    'full_refresh_interval': int(request.form.get('full_refresh_interval', 5)),
                    'show_page_numbers': request.form.get('show_page_numbers') == 'on',
                    'dpi': int(request.form.get('dpi', 150))
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
                    self.app_instance.reader_screen.load_epub(epub_path, dpi=settings_data['dpi'])
                    self.app_instance.reader_screen.current_page = current_page
                    self.app_instance._render_current_screen()

                self.logger.info(f"Settings saved: {settings_data}")
                return redirect(url_for('settings'))

            except Exception as e:
                self.logger.error(f"Failed to save settings: {e}")
                return jsonify({'error': str(e)}), 400

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

    def _load_settings(self):
        """Load settings from settings.json"""
        settings_file = 'settings.json'
        default_settings = {
            'font_size': 12,
            'full_refresh_interval': 5,
            'show_page_numbers': True,
            'dpi': 150
        }

        if os.path.exists(settings_file):
            try:
                with open(settings_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.error(f"Failed to load settings: {e}")
                return default_settings
        else:
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
        body {
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }
        h1, h2 {
            color: #333;
        }
        .section {
            background: white;
            padding: 20px;
            margin: 20px 0;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
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
    </style>
</head>
<body>
    <h1>📚 PiBook Manager</h1>

    <!-- Remote Control -->
    <div class="section">
        <h2>🎮 Remote Control</h2>
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
        <div class="controls" style="margin-top: 10px;">
            <button class="btn btn-secondary" onclick="window.location.href='/settings'">⚙️ Settings</button>
        </div>
    </div>

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

    <script>
        function control(action) {
            fetch('/control/' + action)
                .then(response => response.json())
                .then(data => {
                    console.log('Action:', action, 'Status:', data.status);
                })
                .catch(error => console.error('Error:', error));
        }
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
                <label for="font_size">Font Size</label>
                <input type="number" id="font_size" name="font_size"
                       value="{{ settings.font_size }}" min="8" max="24" step="1">
                <p class="help-text">Font size for EPUB rendering (8-24)</p>
            </div>

            <div class="form-group">
                <label for="dpi">DPI (Resolution)</label>
                <input type="number" id="dpi" name="dpi"
                       value="{{ settings.dpi }}" min="72" max="300" step="1">
                <p class="help-text">Rendering resolution (72-300). Higher = sharper but slower</p>
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

            <button type="submit" class="btn">Save Settings</button>
        </form>

        <button class="btn btn-secondary" onclick="window.location.href='/'">Back to Library</button>
    </div>
</body>
</html>
'''
