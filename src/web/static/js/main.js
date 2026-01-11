// PiBook Web Interface - Main JavaScript

// Navigation
function switchSection(sectionId) {
    // Hide all sections
    document.querySelectorAll('.content-section').forEach(section => {
        section.classList.remove('active');
    });

    // Remove active from all nav items
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.remove('active');
    });

    // Show selected section
    const section = document.getElementById(sectionId);
    if (section) {
        section.classList.add('active');
    }

    // Highlight active nav item
    const navItem = document.querySelector(`[data-section="${sectionId}"]`);
    if (navItem) {
        navItem.classList.add('active');
    }

    // Auto-refresh system stats when navigating to navigation section
    if (sectionId === 'navigation') {
        refreshSystemStats();
    }
}

// File Upload
function uploadFile(event) {
    event.preventDefault();
    const form = event.target;
    const formData = new FormData(form);

    fetch('/upload', {
        method: 'POST',
        body: formData
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                location.reload();
            } else {
                alert('Upload failed: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(error => {
            alert('Upload error: ' + error.message);
        });
}

// File Delete
function deleteFile(filename) {
    if (!confirm(`Delete "${filename}"?`)) {
        return;
    }

    fetch('/delete/' + encodeURIComponent(filename), {
        method: 'POST'
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                location.reload();
            } else {
                alert('Delete failed: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(error => {
            alert('Delete error: ' + error.message);
        });
}

// Settings Form
document.addEventListener('DOMContentLoaded', function () {
    const settingsForm = document.getElementById('settings-form');
    if (settingsForm) {
        settingsForm.addEventListener('submit', function (e) {
            e.preventDefault();

            const formData = new FormData(this);
            const data = {};

            // Convert form data to object
            for (let [key, value] of formData.entries()) {
                if (key === 'show_page_numbers' || key === 'wifi_while_reading' || key === 'sleep_enabled') {
                    data[key] = true;
                } else {
                    data[key] = isNaN(value) ? value : parseFloat(value);
                }
            }

            // Add unchecked checkboxes as false
            ['show_page_numbers', 'wifi_while_reading', 'sleep_enabled'].forEach(field => {
                if (!(field in data)) {
                    data[field] = false;
                }
            });

            // Save settings
            fetch('/save_settings', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(data)
            })
                .then(response => response.json())
                .then(result => {
                    const messageDiv = document.getElementById('settings-message');
                    if (result.success) {
                        messageDiv.className = 'message success';
                        messageDiv.innerHTML = '<strong>✓ Settings saved successfully!</strong><br>Changes will take effect on next restart.';
                        messageDiv.style.display = 'block';
                        messageDiv.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

                        // Reload CPU voltage after short delay
                        setTimeout(() => {
                            fetch('/api/cpu_voltage')
                                .then(response => response.json())
                                .then(data => {
                                    const statusEl = document.getElementById('voltage-status');
                                    if (statusEl && data.voltage) {
                                        statusEl.textContent = 'Current CPU Voltage: ' + data.voltage + ' (Undervolt: ' + data.undervolt_setting + ')';
                                    }
                                });
                        }, 500);
                    } else {
                        throw new Error(result.error || 'Save failed');
                    }
                })
                .catch(error => {
                    const messageDiv = document.getElementById('settings-message');
                    messageDiv.className = 'message error';
                    messageDiv.innerHTML = '<strong>❌ Error saving settings!</strong><br>' + error.message;
                    messageDiv.style.display = 'block';
                    messageDiv.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                });
        });
    }

    // Load current CPU voltage
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
});

// Terminal Functions
function setCommand(cmd) {
    document.getElementById('terminal-input').value = cmd;
    document.getElementById('terminal-input').focus();
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
                // Show stderr in orange
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
    output.innerHTML = '<span style="color: #4CAF50;">Terminal cleared</span><br>';
}

function copyOutput() {
    const output = document.getElementById('terminal-output');
    const text = output.innerText;
    navigator.clipboard.writeText(text).then(() => {
        appendToTerminal('<span style="color: #4CAF50;">✓ Output copied to clipboard</span>');
    }).catch(err => {
        appendToTerminal('<span style="color: #f44336;">✗ Failed to copy: ' + err.message + '</span>');
    });
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Enter key support for terminal
document.addEventListener('DOMContentLoaded', function () {
    const terminalInput = document.getElementById('terminal-input');
    if (terminalInput) {
        terminalInput.addEventListener('keypress', function (e) {
            if (e.key === 'Enter') {
                executeCommand();
            }
        });
    }
});

// System Stats
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
                if (temp < 60) {
                    tempEl.style.color = '#4CAF50'; // Green
                } else if (temp < 70) {
                    tempEl.style.color = '#ff9800'; // Orange
                } else {
                    tempEl.style.color = '#f44336'; // Red
                }
            }

            // Update CPU Voltage
            const voltageEl = document.getElementById('cpu-voltage');
            if (voltageEl && data.cpu_voltage) {
                voltageEl.textContent = data.cpu_voltage;
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

// Remote Control Functions
function sendCommand(command) {
    fetch('/remote/' + command, {
        method: 'POST'
    })
        .then(response => response.json())
        .then(data => {
            if (!data.success) {
                alert('Command failed: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(error => {
            alert('Error: ' + error.message);
        });
}
