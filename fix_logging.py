#!/usr/bin/env python3
# Enable debug logging - simpler approach

lines = []
with open('config/config.yaml', 'r', encoding='utf-8') as f:
    for line in f:
        if 'level: "WARNING"' in line:
            lines.append('  level: "DEBUG"              # Changed from WARNING for troubleshooting\r\n')
        elif 'file: "/tmp/pibook.log"' in line:
            lines.append('  file: "/home/pi/PiBook/logs/pibook.log"  # Persistent log file (not /tmp)\r\n')
        elif 'console: false' in line and 'logging' in ''.join(lines[-5:]):
            lines.append('  console: true               # Enable console output for debugging\r\n')
        elif 'max_size: "1MB"' in line:
            lines.append('  max_size: "10MB"            # Increased from 1MB for more history\r\n')
        else:
            lines.append(line)

with open('config/config.yaml', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("Debug logging enabled successfully")
