class IPScannerScreen:
    """
    IP Scanner screen - scans local network and displays devices
    """

    def __init__(self, width: int = 800, height: int = 480, font_size: int = 18, battery_monitor=None):
        """
        Initialize IP scanner screen

        Args:
            width: Screen width
            height: Screen height
            font_size: Base font size
            battery_monitor: Optional BatteryMonitor instance
        """
        self.width = width
        self.height = height
        self.font_size = font_size
        self.battery_monitor = battery_monitor
        self.logger = logging.getLogger(__name__)

        # Load fonts
        try:
            self.font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_size)
            self.title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
            self.small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
        except:
            self.font = ImageFont.load_default()
            self.title_font = ImageFont.load_default()
            self.small_font = ImageFont.load_default()

        # Scan state
        self.devices: List[Dict[str, str]] = []
        self.scanning = False
        self.scan_progress = 0
        self.current_page = 0
        self.items_per_page = 17  # Increased from 12 to 17 (fits on 480px height)

    def start_scan(self):
        """Start network scan in background"""
        import threading
        if not self.scanning:
            self.scanning = True
            self.scan_progress = 0
            self.devices = []
            thread = threading.Thread(target=self._scan_network, daemon=True)
            thread.start()

    def _scan_network(self):
        """Scan the local network for devices"""
        try:
            # Get local IP and network
            local_ip = get_ip_address()
            if local_ip == "No Network":
                self.scanning = False
                return

            # Extract network prefix (e.g., 192.168.1)
            ip_parts = local_ip.split('.')
            network_prefix = '.'.join(ip_parts[:3])
            network = f"{network_prefix}.0/24"

            self.logger.info(f"Scanning network {network}")

            # Try using arp-scan first (much faster)
            try:
                self.scan_progress = 10
                self.logger.info("Trying arp-scan...")
                result = subprocess.run(
                    ['sudo', 'arp-scan', '--localnet', '--interface=wlan0'],
                    capture_output=True,
                    text=True,
                    timeout=30
                )

                self.logger.info(f"arp-scan return code: {result.returncode}")
                if result.returncode == 0:
                    self.logger.info("Using arp-scan for network discovery")
                    self.logger.debug(f"arp-scan output: {result.stdout}")
                    self._parse_arp_scan_output(result.stdout)
                    self.scanning = False
                    self.scan_progress = 100
                    return
                else:
                    self.logger.warning(f"arp-scan failed with stderr: {result.stderr}")

            except FileNotFoundError:
                self.logger.info("arp-scan not installed, falling back to nmap")
            except subprocess.TimeoutExpired:
                self.logger.warning("arp-scan timed out, falling back to nmap")
            except Exception as e:
                self.logger.error(f"arp-scan error: {e}", exc_info=True)

            # Try nmap as second option
            try:
                self.scan_progress = 20
                self.logger.info("Trying nmap...")
                result = subprocess.run(
                    ['nmap', '-sn', network],
                    capture_output=True,
                    text=True,
                    timeout=60
                )

                self.logger.info(f"nmap return code: {result.returncode}")
                if result.returncode == 0:
                    self.logger.info("Using nmap for network discovery")
                    self.logger.debug(f"nmap output: {result.stdout}")
                    self._parse_nmap_output(result.stdout)
                    self.scanning = False
                    self.scan_progress = 100
                    return
                else:
                    self.logger.warning(f"nmap failed with stderr: {result.stderr}")

            except FileNotFoundError:
                self.logger.info("nmap not installed, falling back to ping sweep")
            except subprocess.TimeoutExpired:
                self.logger.warning("nmap timed out, falling back to ping sweep")
            except Exception as e:
                self.logger.error(f"nmap error: {e}", exc_info=True)

            # Fall back to ping sweep (slowest but most reliable)
            self.logger.info("Using ping sweep for network discovery")
            self.scan_progress = 0

            # Scan range 1-254
            for i in range(1, 255):
                if not self.scanning:
                    break

                ip = f"{network_prefix}.{i}"
                self.scan_progress = int((i / 254) * 100)

                # Ping the IP (quick timeout)
                try:
                    result = subprocess.run(
                        ['ping', '-c', '1', '-W', '1', ip],
                        capture_output=True,
                        timeout=2
                    )

                    if result.returncode == 0:
                        # Get hostname
                        hostname = self._get_hostname(ip)
                        self.devices.append({
                            'ip': ip,
                            'hostname': hostname
                        })
                        self.logger.info(f"Found device: {ip} ({hostname})")

                except Exception as e:
                    self.logger.debug(f"Error pinging {ip}: {e}")
                    continue

            self.scanning = False
            self.scan_progress = 100
            self.logger.info(f"Scan complete. Found {len(self.devices)} devices")

        except Exception as e:
            self.logger.error(f"Network scan error: {e}", exc_info=True)
            self.scanning = False

    def _parse_arp_scan_output(self, output: str):
        """Parse arp-scan output and extract devices with vendor info"""
        lines = output.strip().split('\n')
        for line in lines:
            # arp-scan output format: IP    MAC    Vendor/Hostname
            # Skip header/footer lines
            if line and not line.startswith('Interface:') and not line.startswith('Starting') and not line.startswith('Ending') and not line.startswith('Packets'):
                parts = line.split('\t')  # arp-scan uses tabs
                if len(parts) < 2:
                    parts = line.split()  # Fallback to spaces

                if len(parts) >= 2:
                    # Check if first part looks like an IP
                    ip = parts[0].strip()
                    if ip.count('.') == 3:
                        try:
                            # Validate IP format
                            octets = ip.split('.')
                            if all(0 <= int(octet) <= 255 for octet in octets):
                                # Try to get vendor name from arp-scan output (3rd column)
                                vendor = None
                                if len(parts) >= 3:
                                    vendor = ' '.join(parts[2:]).strip()
                                    # Clean up vendor name
                                    if vendor and vendor != '(Unknown)':
                                        # Remove common suffixes
                                        vendor = vendor.replace(', Inc.', '').replace(' Inc.', '')
                                        vendor = vendor.replace(', Ltd.', '').replace(' Ltd.', '')
                                        vendor = vendor.replace(' Corporation', '').replace(' Corp.', '')

                                # Try to get proper hostname
                                hostname = self._get_hostname(ip, vendor)

                                self.devices.append({
                                    'ip': ip,
                                    'hostname': hostname
                                })
                                self.logger.info(f"Found device: {ip} ({hostname})")
                        except:
                            continue

    def _parse_nmap_output(self, output: str):
        """Parse nmap output and extract devices"""
        lines = output.strip().split('\n')
        for line in lines:
            # nmap output includes lines like: "Nmap scan report for 192.168.1.1"
            if 'Nmap scan report for' in line:
                parts = line.split()
                ip = parts[-1]
                # Remove parentheses if present
                ip = ip.strip('()')

                # Validate IP
                if ip.count('.') == 3:
                    try:
                        octets = ip.split('.')
                        if all(0 <= int(octet) <= 255 for octet in octets):
                            hostname = self._get_hostname(ip)
                            self.devices.append({
                                'ip': ip,
                                'hostname': hostname
                            })
                            self.logger.info(f"Found device: {ip} ({hostname})")
                    except:
                        continue

    def _get_hostname(self, ip: str, vendor: str = None) -> str:
        """Get hostname for an IP address with multiple methods"""
        try:
            # Set socket timeout for faster lookups
            socket.setdefaulttimeout(1.0)

            # Try reverse DNS lookup
            hostname = socket.gethostbyaddr(ip)[0]

            # Don't return IP as hostname
            if hostname != ip:
                # Clean up hostname (remove domain suffix for brevity)
                hostname = hostname.split('.')[0]
                return hostname

        except (socket.herror, socket.gaierror, socket.timeout):
            pass
        except Exception as e:
            self.logger.debug(f"Hostname lookup error for {ip}: {e}")

        # Try mDNS/Avahi lookup for .local hostnames
        try:
            # Try common mDNS patterns
            for suffix in ['.local', '.home', '.lan']:
                try:
                    result = socket.gethostbyname(f"{ip.split('.')[-1]}{suffix}")
                    if result == ip:
                        return f"Device-{ip.split('.')[-1]}"
                except:
                    pass
        except:
            pass

        # Try getfqdn as fallback
        try:
            fqdn = socket.getfqdn(ip)
            if fqdn and fqdn != ip:
                return fqdn.split('.')[0]
        except:
            pass

        # Use vendor name if available
        if vendor and vendor != '(Unknown)':
            return vendor

        # Last resort: descriptive unknown
        return f"Device-{ip.split('.')[-1]}"

    def next_page(self):
        """Move to next page"""
        if len(self.devices) > 0:
            total_pages = (len(self.devices) + self.items_per_page - 1) // self.items_per_page
            self.current_page = (self.current_page + 1) % total_pages

    def prev_page(self):
        """Move to previous page"""
        if len(self.devices) > 0:
            total_pages = (len(self.devices) + self.items_per_page - 1) // self.items_per_page
            self.current_page = (self.current_page - 1 + total_pages) % total_pages

    def _draw_battery_icon(self, draw: ImageDraw.Draw, x: int, y: int, percentage: int, is_charging: bool = False):
        """
        Draw battery icon with percentage and charging indicator
        (Same implementation as MainMenuScreen)
        """
        # Battery body (20x10 rectangle)
        battery_width = 25
        battery_height = 12
        battery_x = x - battery_width - 5
        battery_y = y

        # Draw battery outline
        draw.rectangle(
            [(battery_x, battery_y), (battery_x + battery_width, battery_y + battery_height)],
            outline=0,
            width=2
        )

        # Draw battery terminal (small rectangle on right)
        terminal_width = 2
        terminal_height = 6
        terminal_x = battery_x + battery_width
        terminal_y = battery_y + (battery_height - terminal_height) // 2
        draw.rectangle(
            [(terminal_x, terminal_y), (terminal_x + terminal_width, terminal_y + terminal_height)],
            fill=0
        )

        # Fill battery based on percentage
        if percentage > 0:
            fill_width = int((battery_width - 4) * (percentage / 100))
            draw.rectangle(
                [(battery_x + 2, battery_y + 2),
                 (battery_x + 2 + fill_width, battery_y + battery_height - 2)],
                fill=0
            )

        # Draw charging indicator (lightning bolt) if charging
        if is_charging:
            bolt_center_x = battery_x + battery_width // 2
            bolt_center_y = battery_y + battery_height // 2
            # Larger, more visible lightning bolt
            bolt_points = [
                (bolt_center_x + 2, bolt_center_y - 6),    # Top tip
                (bolt_center_x - 2, bolt_center_y - 1),    # Upper left
                (bolt_center_x + 3, bolt_center_y - 1),    # Upper right
                (bolt_center_x - 2, bolt_center_y + 6),    # Bottom tip
                (bolt_center_x + 2, bolt_center_y + 1),    # Lower right
                (bolt_center_x - 3, bolt_center_y + 1),    # Lower left
            ]
            # Draw white bolt with black outline for visibility
            draw.polygon(bolt_points, fill=1, outline=0)

        # Draw percentage text to the left
        percentage_text = f"{percentage}%"
        try:
            bbox = draw.textbbox((0, 0), percentage_text, font=self.font)
            text_width = bbox[2] - bbox[0]
        except:
            text_width = len(percentage_text) * 8

        text_x = battery_x - text_width - 5
        draw.text((text_x, y), percentage_text, font=self.font, fill=0)

    def render(self) -> Image.Image:
        """Render IP scanner screen"""
        # Create white background
        image = Image.new('1', (self.width, self.height), 1)
        draw = ImageDraw.Draw(image)

        # Draw battery status in top-right corner
        if self.battery_monitor:
            battery_percentage = self.battery_monitor.get_percentage()
            is_charging = self.battery_monitor.is_charging()
            self._draw_battery_icon(draw, self.width - 10, 5, battery_percentage, is_charging)

        # Draw title
        draw.text((40, 30), "IP Scanner", font=self.title_font, fill=0)
        draw.line([(40, 65), (self.width - 40, 65)], fill=0, width=2)

        # Show local IP
        local_ip = get_ip_address()
        draw.text((40, 75), f"Local IP: {local_ip}", font=self.font, fill=0)

        if self.scanning:
            # Show scanning progress
            draw.text((40, 110), f"Scanning network... {self.scan_progress}%", font=self.font, fill=0)

            # Draw progress bar
            bar_width = self.width - 80
            bar_height = 20
            bar_x = 40
            bar_y = 140

            # Outline
            draw.rectangle(
                [(bar_x, bar_y), (bar_x + bar_width, bar_y + bar_height)],
                outline=0,
                width=2
            )

            # Fill
            fill_width = int(bar_width * (self.scan_progress / 100))
            if fill_width > 0:
                draw.rectangle(
                    [(bar_x + 2, bar_y + 2), (bar_x + fill_width - 2, bar_y + bar_height - 2)],
                    fill=0
                )

            draw.text((40, 170), f"Found {len(self.devices)} devices so far", font=self.small_font, fill=0)

        elif len(self.devices) == 0:
            # No devices found yet
            draw.text((40, 110), "No devices found.", font=self.font, fill=0)
            draw.text((40, 140), "Press button to start scan", font=self.small_font, fill=0)

        else:
            # Display device list with pagination
            total_pages = (len(self.devices) + self.items_per_page - 1) // self.items_per_page

            draw.text((40, 100), f"Found {len(self.devices)} devices (Page {self.current_page + 1}/{total_pages}):", font=self.font, fill=0)

            y = 130
            line_height = 20  # Reduced to 20 to fit 17 items

            # Calculate visible range based on current page
            start_idx = self.current_page * self.items_per_page
            end_idx = min(start_idx + self.items_per_page, len(self.devices))

            for i in range(start_idx, end_idx):
                device = self.devices[i]

                # Draw IP address
                draw.text((40, y), device['ip'], font=self.font, fill=0)

                # Draw hostname on the same line (right side)
                hostname = device['hostname']
                if len(hostname) > 35:
                    hostname = hostname[:32] + "..."
                draw.text((200, y), hostname, font=self.small_font, fill=0)

                y += line_height

        # Draw instructions at bottom
        if self.scanning:
            instruction = "Scanning... Please wait"
        elif len(self.devices) > 0:
            instruction = "Press: Next  |  Hold: Scan  |  Menu: Home"
        else:
            instruction = "Hold: Start Scan  |  Menu: Home"

        try:
            bbox = draw.textbbox((0, 0), instruction, font=self.small_font)
            instr_width = bbox[2] - bbox[0]
        except:
            instr_width = len(instruction) * 7

        instr_x = (self.width - instr_width) // 2
        draw.text((instr_x, self.height - 30), instruction, font=self.small_font, fill=0)

        return image
