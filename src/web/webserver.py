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

        # Initialize To-Do module
        from apps.todo import TodoManager, todo_bp, init_routes
        self.todo_manager = TodoManager(app_instance=app_instance)
        init_routes(self.todo_manager)
        self.flask_app.register_blueprint(todo_bp)
        self.logger.info("Registered To-Do Blueprint")

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

        # IP Scanner API Routes
        @self.flask_app.route('/api/ipscanner/status')
        def ipscanner_status():
            """Get current IP scanner status"""
            try:
                from src.apps.ipscanner.screen import get_ip_address

                scanner = self.app_instance.ip_scanner_screen
                return jsonify({
                    'scanning': scanner.scanning,
                    'progress': scanner.scan_progress,
                    'devices': scanner.devices,
                    'local_ip': get_ip_address()
                })
            except Exception as e:
                self.logger.error(f"IP scanner status error: {e}")
                return jsonify({'error': str(e)}), 500

        @self.flask_app.route('/api/ipscanner/scan', methods=['POST'])
        def ipscanner_start():
            """Start IP scanner"""
            try:
                scanner = self.app_instance.ip_scanner_screen

                if scanner.scanning:
                    return jsonify({'status': 'already_scanning'})

                scanner.start_scan()
                return jsonify({'status': 'started'})
            except Exception as e:
                self.logger.error(f"IP scanner start error: {e}")
                return jsonify({'error': str(e)}), 500

        # Klipper Printer Discovery API
        # Store discovered printers
        self.klipper_printers = []
        self.klipper_scanning = False

        @self.flask_app.route('/api/klipper/printers')
        def klipper_printers():
            """Get list of discovered Klipper printers"""
            return jsonify({
                'printers': self.klipper_printers,
                'scanning': self.klipper_scanning
            })

        @self.flask_app.route('/api/klipper/scan', methods=['POST'])
        def klipper_scan():
            """Scan network for Klipper printers"""
            import threading

            if self.klipper_scanning:
                return jsonify({'status': 'scanning'})

            def scan_for_klipper():
                self.klipper_scanning = True
                self.klipper_printers = []

                try:
                    # Get devices from IP scanner
                    scanner = self.app_instance.ip_scanner_screen

                    # If no devices scanned yet, trigger a scan
                    if not scanner.devices and not scanner.scanning:
                        scanner.start_scan()
                        # Wait for scan to complete
                        import time
                        while scanner.scanning:
                            time.sleep(0.5)

                    # Check each device for Klipper (port 80 and 7125)
                    for device in scanner.devices:
                        ip = device['ip']

                        # Check if port 7125 (Moonraker API) is open
                        if self._check_port(ip, 7125):
                            printer_info = self._get_klipper_info(ip, device.get('hostname', ''))
                            if printer_info:
                                self.klipper_printers.append(printer_info)

                    self.logger.info(f"Found {len(self.klipper_printers)} Klipper printers")

                except Exception as e:
                    self.logger.error(f"Klipper scan error: {e}")
                finally:
                    self.klipper_scanning = False

            thread = threading.Thread(target=scan_for_klipper, daemon=True)
            thread.start()

            return jsonify({'status': 'started'})

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
                # Get JSON data from request
                data = request.get_json()
                
                settings_data = {
                    'zoom': float(data.get('zoom', 1.0)),
                    'full_refresh_interval': int(data.get('full_refresh_interval', 10)),
                    'show_page_numbers': data.get('show_page_numbers', False),
                    'wifi_while_reading': data.get('wifi_while_reading', False),
                    'sleep_enabled': data.get('sleep_enabled', False),
                    'sleep_message': data.get('sleep_message', 'Shh I\'m sleeping'),
                    'sleep_timeout': int(data.get('sleep_timeout', 120)),
                    'shutdown_message': data.get('shutdown_message', 'OFF'),
                    'items_per_page': int(data.get('items_per_page', 4)),
                    'undervolt': int(data.get('undervolt', -2)),
                    'boot_cores': int(data.get('boot_cores', 4))
                }

                self._save_settings(settings_data)
                
                # Force SettingsManager to reload from file so changes take effect immediately
                self.app_instance.settings_manager.settings = self.app_instance.settings_manager.load()
                self.app_instance.settings = self.app_instance.settings_manager.get_all()
                self.logger.info("Settings reloaded in app instance from file")

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

                # Update /boot/firmware/config.txt if boot_cores changed
                boot_cores_error = None
                old_boot_cores = self.app_instance.config.get('power.boot_cores', 4)
                new_boot_cores = settings_data['boot_cores']
                self.app_instance.config.set('power.boot_cores', new_boot_cores)
                if old_boot_cores != new_boot_cores:
                    try:
                        self._apply_boot_cores(new_boot_cores)
                        self.logger.info(f"Boot cores changed from {old_boot_cores} to {new_boot_cores} - reboot required")
                    except Exception as e:
                        self.logger.error(f"Failed to apply boot_cores to boot config: {e}")
                        boot_cores_error = str(e)

                self.logger.info(f"Settings saved: {settings_data}")

                # Return JSON for AJAX requests, redirect for normal form submission
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.accept_mimetypes.accept_json:
                    result = {'status': 'success', 'message': 'Settings saved successfully'}
                    if undervolt_error:
                        result['undervolt_warning'] = f'Settings saved but undervolt update failed: {undervolt_error}'
                    if boot_cores_error:
                        result['boot_cores_warning'] = f'Settings saved but boot_cores update failed: {boot_cores_error}'
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
                
                # Intercept 'git pull' to use safe update script
                if command.strip() == 'git pull':
                    command = 'bash /home/pi/PiBook/scripts/safe_update.sh'
                    self.logger.info("Intercepted git pull, using safe update script")
                
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

        # Bluetooth Management APIs
        @self.flask_app.route('/api/bluetooth/status')
        def bluetooth_status():
            """Get Bluetooth status and paired devices"""
            try:
                import subprocess
                
                # Check if Bluetooth is powered on
                result = subprocess.run(['bluetoothctl', 'show'], capture_output=True, text=True, timeout=5)
                powered = 'Powered: yes' in result.stdout
                
                # Get paired devices
                result = subprocess.run(['bluetoothctl', 'paired-devices'], capture_output=True, text=True, timeout=5)
                paired_devices = []
                for line in result.stdout.strip().split('\n'):
                    if line.startswith('Device '):
                        parts = line.split(' ', 2)
                        if len(parts) >= 3:
                            paired_devices.append({'mac': parts[1], 'name': parts[2]})
                
                return jsonify({'powered': powered, 'paired_devices': paired_devices})
            except Exception as e:
                self.logger.error(f"Bluetooth status check failed: {e}")
                return jsonify({'error': str(e)}), 500

        @self.flask_app.route('/api/bluetooth/power', methods=['POST'])
        def bluetooth_power():
            """Toggle Bluetooth power"""
            try:
                import subprocess
                data = request.get_json()
                power_on = data.get('power', False)
                action = 'power_on' if power_on else 'power_off'
                
                result = subprocess.run(['sudo', '/home/pi/PiBook/scripts/bluetooth_helper.sh', action], 
                                      capture_output=True, text=True, timeout=10)
                
                if result.returncode == 0:
                    return jsonify({'success': True, 'powered': power_on})
                else:
                    return jsonify({'error': result.stderr}), 500
            except Exception as e:
                self.logger.error(f"Bluetooth power toggle failed: {e}")
                return jsonify({'error': str(e)}), 500

        @self.flask_app.route('/api/bluetooth/scan', methods=['POST'])
        def bluetooth_scan():
            """Start/stop Bluetooth scanning"""
            try:
                import subprocess
                data = request.get_json()
                scan_on = data.get('scan', False)
                action = 'scan_on' if scan_on else 'scan_off'
                
                result = subprocess.run(['sudo', '/home/pi/PiBook/scripts/bluetooth_helper.sh', action], 
                                      capture_output=True, text=True, timeout=10)
                
                return jsonify({'success': True, 'scanning': scan_on})
            except Exception as e:
                self.logger.error(f"Bluetooth scan toggle failed: {e}")
                return jsonify({'error': str(e)}), 500

        @self.flask_app.route('/api/bluetooth/devices')
        def bluetooth_devices():
            """Get discovered Bluetooth devices"""
            try:
                import subprocess
                result = subprocess.run(['bluetoothctl', 'devices'], capture_output=True, text=True, timeout=5)
                devices = []
                for line in result.stdout.strip().split('\n'):
                    if line.startswith('Device '):
                        parts = line.split(' ', 2)
                        if len(parts) >= 3:
                            devices.append({'mac': parts[1], 'name': parts[2]})
                
                return jsonify({'devices': devices})
            except Exception as e:
                self.logger.error(f"Bluetooth device list failed: {e}")
                return jsonify({'error': str(e)}), 500

        @self.flask_app.route('/api/bluetooth/pair', methods=['POST'])
        def bluetooth_pair():
            """Pair with a Bluetooth device"""
            try:
                import subprocess
                data = request.get_json()
                mac = data.get('mac')
                pin = data.get('pin', '')
                
                if not mac:
                    return jsonify({'error': 'MAC address required'}), 400
                
                # Run pairing command with optional PIN
                if pin:
                    result = subprocess.run(['sudo', '/home/pi/PiBook/scripts/bluetooth_helper.sh', 'pair', mac, pin], 
                                          capture_output=True, text=True, timeout=30)
                else:
                    result = subprocess.run(['sudo', '/home/pi/PiBook/scripts/bluetooth_helper.sh', 'pair', mac], 
                                          capture_output=True, text=True, timeout=30)
                
                if result.returncode == 0 or 'successful' in result.stdout.lower():
                    return jsonify({'success': True})
                else:
                    return jsonify({'error': result.stderr or result.stdout}), 500
            except Exception as e:
                self.logger.error(f"Bluetooth pairing failed: {e}")
                return jsonify({'error': str(e)}), 500

        @self.flask_app.route('/api/bluetooth/remove', methods=['POST'])
        def bluetooth_remove():
            """Remove a paired Bluetooth device"""
            try:
                import subprocess
                data = request.get_json()
                mac = data.get('mac')
                
                if not mac:
                    return jsonify({'error': 'MAC address required'}), 400
                
                result = subprocess.run(['sudo', '/home/pi/PiBook/scripts/bluetooth_helper.sh', 'remove', mac], 
                                      capture_output=True, text=True, timeout=10)
                
                if result.returncode == 0:
                    return jsonify({'success': True})
                else:
                    return jsonify({'error': result.stderr}), 500
            except Exception as e:
                self.logger.error(f"Bluetooth device removal failed: {e}")
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

                # CPU Speed
                try:
                    with open('/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq', 'r') as f:
                        freq_khz = int(f.read().strip())
                        freq_mhz = freq_khz / 1000
                        stats['cpu_speed'] = f"{freq_mhz:.0f} MHz"
                except:
                    # Fallback to vcgencmd if file not found
                    try:
                        result = subprocess.run(['vcgencmd', 'measure_clock', 'arm'], capture_output=True, text=True, timeout=2)
                        if result.returncode == 0:
                            # Output format: frequency(48)=600000000
                            freq_hz = int(result.stdout.strip().split('=')[1])
                            freq_mhz = freq_hz / 1000000
                            stats['cpu_speed'] = f"{freq_mhz:.0f} MHz"
                        else:
                            stats['cpu_speed'] = 'N/A'
                    except:
                        stats['cpu_speed'] = 'N/A'

                # WiFi Status
                try:
                    result = subprocess.run(['ip', 'link', 'show', 'wlan0'], capture_output=True, text=True, timeout=2)
                    if result.returncode == 0 and ('state UP' in result.stdout or 'UP' in result.stdout):
                        stats['wifi_status'] = 'On'
                    else:
                        stats['wifi_status'] = 'Off'
                except:
                    stats['wifi_status'] = 'Unknown'

                # Bluetooth Status
                try:
                    result = subprocess.run(['systemctl', 'is-active', 'bluetooth'], capture_output=True, text=True, timeout=2)
                    if result.returncode == 0 and result.stdout.strip() == 'active':
                        hci_result = subprocess.run(['hciconfig', 'hci0'], capture_output=True, text=True, timeout=2)
                        if hci_result.returncode == 0 and 'UP RUNNING' in hci_result.stdout:
                            stats['bluetooth_status'] = 'On'
                        else:
                            stats['bluetooth_status'] = 'On (No Device)'
                    else:
                        stats['bluetooth_status'] = 'Off'
                except:
                    stats['bluetooth_status'] = 'Unknown'

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

    def _check_port(self, ip: str, port: int) -> bool:
        """Check if a port is open on the given IP"""
        import socket
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((ip, port))
            sock.close()
            return result == 0
        except:
            return False

    def _get_klipper_info(self, ip: str, hostname: str = '') -> dict:
        """Get Klipper printer info from Moonraker API"""
        import urllib.request
        import json as json_lib

        try:
            # Get printer info from Moonraker API
            base_url = f"http://{ip}:7125"

            printer_info = {
                'ip': ip,
                'hostname': hostname,
                'state': 'unknown',
                'klipper_version': None,
                'extruder_temp': None,
                'extruder_target': None,
                'bed_temp': None,
                'bed_target': None,
                'progress': None
            }

            # Get server info (includes Klipper version)
            try:
                req = urllib.request.Request(f"{base_url}/server/info", method='GET')
                req.add_header('Content-Type', 'application/json')
                with urllib.request.urlopen(req, timeout=5) as response:
                    data = json_lib.loads(response.read().decode())
                    if 'result' in data:
                        printer_info['klipper_version'] = data['result'].get('klippy_state', 'unknown')
            except Exception as e:
                self.logger.debug(f"Failed to get server info from {ip}: {e}")

            # Get printer state
            try:
                req = urllib.request.Request(f"{base_url}/printer/info", method='GET')
                req.add_header('Content-Type', 'application/json')
                with urllib.request.urlopen(req, timeout=5) as response:
                    data = json_lib.loads(response.read().decode())
                    if 'result' in data:
                        printer_info['state'] = data['result'].get('state', 'unknown')
            except Exception as e:
                self.logger.debug(f"Failed to get printer info from {ip}: {e}")

            # Get temperature data
            try:
                req = urllib.request.Request(
                    f"{base_url}/printer/objects/query?extruder&heater_bed&print_stats",
                    method='GET'
                )
                req.add_header('Content-Type', 'application/json')
                with urllib.request.urlopen(req, timeout=5) as response:
                    data = json_lib.loads(response.read().decode())
                    if 'result' in data and 'status' in data['result']:
                        status = data['result']['status']

                        # Extruder temps
                        if 'extruder' in status:
                            printer_info['extruder_temp'] = status['extruder'].get('temperature', 0)
                            printer_info['extruder_target'] = status['extruder'].get('target', 0)

                        # Bed temps
                        if 'heater_bed' in status:
                            printer_info['bed_temp'] = status['heater_bed'].get('temperature', 0)
                            printer_info['bed_target'] = status['heater_bed'].get('target', 0)

                        # Print progress
                        if 'print_stats' in status:
                            print_stats = status['print_stats']
                            state = print_stats.get('state', '')
                            if state == 'printing':
                                printer_info['state'] = 'printing'
                                printer_info['progress'] = print_stats.get('progress', 0)
                            elif state == 'complete':
                                printer_info['state'] = 'complete'
                            elif state == 'standby':
                                printer_info['state'] = 'ready'

            except Exception as e:
                self.logger.debug(f"Failed to get temperature data from {ip}: {e}")

            return printer_info

        except Exception as e:
            self.logger.error(f"Failed to get Klipper info from {ip}: {e}")
            return None

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
            'undervolt': self.app_instance.config.get('power.undervolt', -2),
            'boot_cores': self.app_instance.config.get('power.boot_cores', 4)
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
                json.dump(settings_data, f, indent=2)
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

    def _apply_boot_cores(self, num_cores):
        """Apply boot CPU cores setting via maxcpus in /boot/firmware/cmdline.txt using sudo helper script"""
        try:
            import subprocess
            script_path = '/home/pi/PiBook/scripts/apply_cpu_cores.sh'

            # Use sudo to run the helper script
            result = subprocess.run(
                ['sudo', script_path, str(num_cores)],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                self.logger.info(f"Successfully applied boot_cores={num_cores} via helper script")
                self.logger.info(result.stdout.strip())
            else:
                self.logger.error(f"Failed to apply boot_cores: {result.stderr}")
                raise Exception(f"Helper script failed: {result.stderr}")

        except subprocess.TimeoutExpired:
            self.logger.error("Timeout applying boot_cores setting")
            raise
        except Exception as e:
            self.logger.error(f"Failed to apply boot_cores: {e}")
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

