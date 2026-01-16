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

    // Auto-refresh system stats when navigating to info or navigation section
    // Load todos and open app when navigating to todo section
    if (sectionId === 'info' || sectionId === 'navigation') {
        refreshSystemStats();
    } else if (sectionId === 'todo') {
        loadTodos();
        openTodoApp();
    } else if (sectionId === 'ipscanner') {
        initIPScanner();
    } else if (sectionId === 'klipper') {
        initKlipper();
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
                    if (result.status === 'success') {
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

            // Update CPU Speed
            const speedEl = document.getElementById('cpu-speed');
            if (speedEl && data.cpu_speed) {
                speedEl.textContent = data.cpu_speed;
            }

            // Update WiFi Status
            const wifiEl = document.getElementById('wifi-status');
            if (wifiEl && data.wifi_status) {
                wifiEl.textContent = data.wifi_status;
                if (data.wifi_status === 'On') {
                    wifiEl.style.color = '#4CAF50';
                } else if (data.wifi_status === 'Off') {
                    wifiEl.style.color = '#f44336';
                }
            }

            // Update Bluetooth Status
            const btEl = document.getElementById('bluetooth-status');
            if (btEl && data.bluetooth_status) {
                btEl.textContent = data.bluetooth_status;
                if (data.bluetooth_status.startsWith('On')) {
                    btEl.style.color = '#4CAF50';
                } else if (data.bluetooth_status === 'Off') {
                    btEl.style.color = '#f44336';
                }
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

            // Update Memory Usage
            const memoryEl = document.getElementById('memory-usage');
            if (memoryEl && data.memory_used && data.memory_total) {
                memoryEl.textContent = `${data.memory_used} / ${data.memory_total}`;
                // Color code based on percentage if available
                if (data.memory_percent) {
                    const percent = parseInt(data.memory_percent);
                    if (percent < 70) {
                        memoryEl.style.color = '#4CAF50'; // Green
                    } else if (percent < 85) {
                        memoryEl.style.color = '#ff9800'; // Orange
                    } else {
                        memoryEl.style.color = '#f44336'; // Red
                    }
                }
            }

            // Update Disk Space
            const diskEl = document.getElementById('disk-free');
            if (diskEl && data.disk_free) {
                if (data.disk_used && data.disk_total) {
                    diskEl.textContent = `${data.disk_free} free`;
                    diskEl.title = `${data.disk_used} used of ${data.disk_total}`;
                } else {
                    diskEl.textContent = data.disk_free;
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

// To-Do List Functions
function loadTodos() {
    fetch('/api/todos')
        .then(response => response.json())
        .then(data => {
            const todoList = document.getElementById('todo-list');
            if (!todoList) return;

            if (data.tasks && data.tasks.length > 0) {
                let html = '';
                data.tasks.forEach(task => {
                    const checkedClass = task.completed ? 'checked' : '';
                    const textStyle = task.completed ? 'text-decoration: line-through; color: #999;' : '';
                    html += `
                        <div style="display: flex; align-items: center; gap: 12px; padding: 12px; background: #f9f9f9; border-radius: 6px; margin-bottom: 8px;">
                            <input type="checkbox" ${task.completed ? 'checked' : ''} 
                                   onclick="toggleTodo('${task.id}')" 
                                   style="width: 20px; height: 20px; cursor: pointer;">
                            <span id="task-text-${task.id}" style="flex: 1; ${textStyle}">${escapeHtml(task.text)}</span>
                            <input type="text" id="task-edit-${task.id}" style="flex: 1; padding: 8px; display: none; border: 2px solid #2196F3; border-radius: 4px;">
                            <button class="btn btn-secondary" onclick="startEditTodo('${task.id}', \`${escapeHtml(task.text).replace(/`/g, '\\`')}\`)" id="edit-btn-${task.id}" style="padding: 8px 16px;">Edit</button>
                            <button class="btn" onclick="saveEditTodo('${task.id}')" id="save-btn-${task.id}" style="padding: 8px 16px; display: none; background: #4CAF50;">Save</button>
                            <button class="btn btn-secondary" onclick="cancelEditTodo('${task.id}', \`${escapeHtml(task.text).replace(/`/g, '\\`')}\`)" id="cancel-btn-${task.id}" style="padding: 8px 16px; display: none;">Cancel</button>
                            <button class="btn btn-danger" onclick="deleteTodo('${task.id}')" id="delete-btn-${task.id}" style="padding: 8px 16px;">Delete</button>
                        </div>
                    `;
                });
                todoList.innerHTML = html;
            } else {
                todoList.innerHTML = '<p style="color: #999; text-align: center; padding: 40px;">No tasks yet. Add one above!</p>';
            }
        })
        .catch(error => {
            console.error('Failed to load todos:', error);
            const todoList = document.getElementById('todo-list');
            if (todoList) {
                todoList.innerHTML = '<p style="color: #f44336; text-align: center; padding: 40px;">Error loading tasks</p>';
            }
        });
}

function startEditTodo(taskId, currentText) {
    // Hide text and edit button, show input and save/cancel buttons
    document.getElementById(`task-text-${taskId}`).style.display = 'none';
    document.getElementById(`edit-btn-${taskId}`).style.display = 'none';
    document.getElementById(`delete-btn-${taskId}`).style.display = 'none';

    const editInput = document.getElementById(`task-edit-${taskId}`);
    editInput.style.display = 'block';
    editInput.value = currentText;
    editInput.focus();

    document.getElementById(`save-btn-${taskId}`).style.display = 'block';
    document.getElementById(`cancel-btn-${taskId}`).style.display = 'block';
}

function cancelEditTodo(taskId, originalText) {
    // Restore original state
    document.getElementById(`task-text-${taskId}`).style.display = 'block';
    document.getElementById(`edit-btn-${taskId}`).style.display = 'block';
    document.getElementById(`delete-btn-${taskId}`).style.display = 'block';

    document.getElementById(`task-edit-${taskId}`).style.display = 'none';
    document.getElementById(`save-btn-${taskId}`).style.display = 'none';
    document.getElementById(`cancel-btn-${taskId}`).style.display = 'none';
}

function saveEditTodo(taskId) {
    const newText = document.getElementById(`task-edit-${taskId}`).value.trim();

    if (!newText) {
        alert('Task description cannot be empty');
        return;
    }

    fetch(`/api/todos/${taskId}`, {
        method: 'PATCH',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ text: newText })
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                loadTodos();
            } else {
                alert('Failed to edit task: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(error => {
            alert('Error editing task: ' + error.message);
        });
}

function addTodo() {
    const input = document.getElementById('new-task-input');
    const text = input.value.trim();

    if (!text) {
        alert('Please enter a task description');
        return;
    }

    fetch('/api/todos', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ text: text })
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                input.value = '';
                loadTodos();
            } else {
                alert('Failed to add task: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(error => {
            alert('Error adding task: ' + error.message);
        });
}

function toggleTodo(taskId) {
    fetch(`/api/todos/${taskId}`, {
        method: 'PUT'
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                loadTodos();
            } else {
                alert('Failed to update task: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(error => {
            alert('Error updating task: ' + error.message);
        });
}

function deleteTodo(taskId) {
    if (!confirm('Delete this task?')) {
        return;
    }

    fetch(`/api/todos/${taskId}`, {
        method: 'DELETE'
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                loadTodos();
            } else {
                alert('Failed to delete task: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(error => {
            alert('Error deleting task: ' + error.message);
        });
}

function openTodoApp() {
    fetch('/remote/open_todo', {
        method: 'POST'
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Optionally show a success message
                console.log('To-Do app opened on PiBook');
            } else {
                alert('Failed to open To-Do app: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(error => {
            alert('Error opening To-Do app: ' + error.message);
        });
}

// Enter key support for todo input
document.addEventListener('DOMContentLoaded', function () {
    const todoInput = document.getElementById('new-task-input');
    if (todoInput) {
        todoInput.addEventListener('keypress', function (e) {
            if (e.key === 'Enter') {
                addTodo();
            }
        });
    }
});

// Bluetooth Management Functions
let bluetoothScanning = false;
let currentPairDevice = null;

// Load Bluetooth status on page load
document.addEventListener('DOMContentLoaded', function () {
    if (document.getElementById('bluetooth_enabled')) {
        refreshBluetoothStatus();

        // Toggle Bluetooth power
        document.getElementById('bluetooth_enabled').addEventListener('change', function () {
            toggleBluetoothPower(this.checked);
        });
    }
});

function refreshBluetoothStatus() {
    fetch('/api/bluetooth/status')
        .then(response => response.json())
        .then(data => {
            const checkbox = document.getElementById('bluetooth_enabled');
            const controls = document.getElementById('bluetooth-controls');

            checkbox.checked = data.powered;
            controls.style.display = data.powered ? 'block' : 'none';

            if (data.powered) {
                updatePairedDevices(data.paired_devices);
            }
        })
        .catch(error => console.error('Bluetooth status check failed:', error));
}

function toggleBluetoothPower(powerOn) {
    fetch('/api/bluetooth/power', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ power: powerOn })
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                document.getElementById('bluetooth-controls').style.display = powerOn ? 'block' : 'none';
                if (powerOn) {
                    refreshBluetoothStatus();
                }
            } else {
                alert('Failed to toggle Bluetooth: ' + (data.error || 'Unknown error'));
                document.getElementById('bluetooth_enabled').checked = !powerOn;
            }
        })
        .catch(error => {
            console.error('Bluetooth power toggle failed:', error);
            alert('Failed to toggle Bluetooth');
            document.getElementById('bluetooth_enabled').checked = !powerOn;
        });
}

// Keep track of all devices found during this scan session
let discoveredDevices = new Map();

function toggleBluetoothScan() {
    bluetoothScanning = !bluetoothScanning;
    const btn = document.getElementById('scan-btn');
    const modal = document.getElementById('scan-modal');

    if (bluetoothScanning) {
        // Start Scanning
        btn.textContent = 'Scanning...';
        modal.style.display = 'block';
        discoveredDevices.clear();
        updateAvailableDevices([]); // Clear UI
    } else {
        // Stop Scanning
        btn.textContent = 'Scan for Devices';
        modal.style.display = 'none';

        // Also call backend to stop scan
        fetch('/api/bluetooth/scan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ scan: false })
        }).catch(e => console.error(e));

        return;
    }

    fetch('/api/bluetooth/scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scan: bluetoothScanning })
    })
        .then(response => response.json())
        .then(data => {
            if (bluetoothScanning) {
                // Poll for devices every 2 seconds
                pollBluetoothDevices();
            }
        })
        .catch(error => {
            console.error('Bluetooth scan toggle failed:', error);
            // Do NOT close the modal on error, let user see it
            // bluetoothScanning = false;
            // modal.style.display = 'none';
            btn.textContent = 'Scan for Devices';

            // Show error in modal
            document.getElementById('available-devices').innerHTML =
                `<p style="color: red; text-align: center;">Scan failed: ${error.message || 'Unknown error'}</p>`;
        });
}

function pollBluetoothDevices() {
    if (!bluetoothScanning) return;

    fetch('/api/bluetooth/devices')
        .then(response => response.json())
        .then(data => {
            if (data.devices) {
                updateAvailableDevices(data.devices);
            }
            if (bluetoothScanning) {
                setTimeout(pollBluetoothDevices, 2000);
            }
        })
        .catch(error => {
            console.error('Device polling failed:', error);
            // Don't stop scanning on poll failure, just retry
            if (bluetoothScanning) {
                setTimeout(pollBluetoothDevices, 2000);
            }
        });
}

function updateAvailableDevices(devices) {
    const container = document.getElementById('available-devices');

    // Add/Update new devices
    devices.forEach(device => {
        discoveredDevices.set(device.mac, device);
    });

    if (discoveredDevices.size === 0) {
        container.innerHTML = '<p style="color: #666;">Scanning...</p>';
        return;
    }

    // Re-render full list (sorted by name)
    container.innerHTML = '';
    Array.from(discoveredDevices.values())
        .sort((a, b) => (a.name || '').localeCompare(b.name || ''))
        .forEach(device => {
            const div = document.createElement('div');
            div.style.cssText = 'padding: 12px; margin: 6px 0; border: 1px solid #eee; background: #f9f9f9; border-radius: 6px; display: flex; justify-content: space-between; align-items: center;';
            div.innerHTML = `
                <div>
                    <strong style="font-size: 1.1em;">${device.name}</strong>
                    <div style="font-size: 0.9em; color: #666; margin-top: 2px;">${device.mac}</div>
                </div>
                <button class="btn" style="padding: 8px 16px;" onclick="pairDevice('${device.mac}', '${device.name}')">Pair</button>
            `;
            container.appendChild(div);
        });
}

function updatePairedDevices(devices) {
    const container = document.getElementById('paired-devices');
    container.innerHTML = '';

    if (devices.length === 0) {
        container.innerHTML = '<p style="color: #666;">No paired devices</p>';
        return;
    }

    devices.forEach(device => {
        const div = document.createElement('div');
        div.style.cssText = 'padding: 8px; margin: 4px 0; border: 1px solid #ddd; border-radius: 4px; display: flex; justify-content: space-between; align-items: center;';
        div.innerHTML = `
            <span><strong>${device.name}</strong><br><small>${device.mac}</small></span>
            <button class="btn" style="padding: 4px 12px; background: #d32f2f;" onclick="removeDevice('${device.mac}')">Remove</button>
        `;
        container.appendChild(div);
    });
}

let currentPairingMac = null;

function pairDevice(mac, name) {
    // Try pairing without PIN first (Works for SSP devices including keyboards)

    currentPairingMac = mac;

    fetch('/api/bluetooth/pair', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mac: mac })
    })
        .then(response => response.json())
        .then(data => {
            // Restore button state (though we might close modal or change UI)
            // But if we fallback to PIN modal, we should probably keep it clean

            if (data.success) {
                if (data.status === 'passkey_required') {
                    showPasskeyModal(data.passkey, data.message);
                } else {
                    alert('Pairing successful!');
                    refreshBluetoothStatus();
                }
            } else {
                // Return to legacy PIN input behavior on failure
                showPinInputModal(name);
            }
        })
        .catch(error => {
            console.error('Pairing failed:', error);
            alert('Pairing request failed. You can try manual PIN entry.');
            showPinInputModal(name);
        });
}

function showPinInputModal(name) {
    document.getElementById('modal-title').innerText = 'Enter PIN';
    document.getElementById('modal-message').innerText = name ? `Enter PIN for ${name}:` : 'Enter PIN for device:';
    document.getElementById('pin-input-container').style.display = 'block';
    document.getElementById('passkey-display-container').style.display = 'none';
    document.getElementById('modal-submit-btn').style.display = 'block';
    document.getElementById('pin-input').value = '';
    document.getElementById('pin-modal').style.display = 'block';
}

function showPasskeyModal(passkey, message) {
    document.getElementById('modal-title').innerText = 'Pairing Code';
    document.getElementById('modal-message').innerText = message;
    document.getElementById('pin-input-container').style.display = 'none';
    document.getElementById('passkey-display-container').style.display = 'block';
    document.getElementById('passkey-display').innerText = passkey;
    document.getElementById('modal-submit-btn').style.display = 'none';
    document.getElementById('pin-modal').style.display = 'block';
}

function closePinModal() {
    document.getElementById('pin-modal').style.display = 'none';
    currentPairingMac = null;
}

function submitPin() {
    const pin = document.getElementById('pin-input').value;
    if (!pin) return;

    fetch('/api/bluetooth/pair', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mac: currentPairingMac, pin: pin })
    })
        .then(response => response.json())
        .then(data => {
            closePinModal();
            if (data.success) {
                alert('Pairing successful!');
                refreshBluetoothStatus();
            } else {
                alert('Pairing failed: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(error => {
            console.error('Pairing failed:', error);
            alert('Pairing failed');
            closePinModal();
        });
}


function removeDevice(mac) {
    if (!confirm('Remove this device?')) return;

    fetch('/api/bluetooth/remove', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mac: mac })
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                refreshBluetoothStatus();
            } else {
                alert('Failed to remove device: ' + (data.error || 'Unknown error'));
            }
        })
        .catch(error => {
            console.error('Device removal failed:', error);
            alert('Failed to remove device');
        });
}
