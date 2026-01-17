#!/bin/bash
# Bluetooth Helper Script for PiBook
# Provides sudo access for Bluetooth operations

case "$1" in
    power_on)
        echo "Powering on Bluetooth..."
        rfkill unblock bluetooth 2>&1
        echo "Bluetooth powered on"
        ;;
    power_off)
        echo "Powering off Bluetooth..."
        rfkill block bluetooth 2>&1
        echo "Bluetooth powered off"
        ;;
    scan_on)
        echo "Starting Bluetooth scan..."
        # Kill any existing scan processes first
        pkill -f "bt_scan_session" 2>/dev/null || true
        sleep 0.5

        # Create a script that keeps bluetoothctl running with scan active
        cat > /tmp/bt_scan_session.sh << 'SCANSCRIPT'
#!/bin/bash
# Keep bluetoothctl running with scan on for extended discovery
# Use a FIFO to keep the process alive
FIFO=/tmp/bt_scan_fifo
rm -f $FIFO
mkfifo $FIFO

# Start bluetoothctl with scan on, reading from FIFO to keep it alive
(
    echo "power on"
    sleep 1
    echo "agent on"
    sleep 0.5
    echo "scan on"
    # Keep alive for 60 seconds
    sleep 60
    echo "scan off"
    echo "quit"
) | bluetoothctl 2>/dev/null

rm -f $FIFO
SCANSCRIPT
        chmod +x /tmp/bt_scan_session.sh

        # Run in background
        nohup /tmp/bt_scan_session.sh >/dev/null 2>&1 &
        echo "Scan started (will run for ~60 seconds)"
        ;;
    scan_off)
        echo "Stopping Bluetooth scan..."
        # Kill the scan session
        pkill -f "bt_scan_session" 2>/dev/null || true
        pkill -f "bluetoothctl" 2>/dev/null || true
        sleep 0.5
        # Send scan off command
        echo -e "scan off\nquit" | bluetoothctl 2>/dev/null || true
        echo "Scan stopped"
        ;;
    pair)
        # $2 = MAC address, $3 = PIN (optional)
        MAC="$2"
        PIN="$3"

        echo "=== Pairing with device $MAC ===" >> /tmp/bt_pair_debug.log
        date >> /tmp/bt_pair_debug.log

        # Kill any existing bluetoothctl processes to avoid agent conflicts
        pkill -f "bluetoothctl" 2>/dev/null || true
        sleep 0.5

        # Create a temporary expect script file to avoid quoting issues
        cat > /tmp/bt_pair.exp << 'EXPECTSCRIPT'
#!/usr/bin/expect -f
log_file -a /tmp/bt_pair_debug.log
set timeout 30
set mac [lindex $argv 0]
set pin [lindex $argv 1]

send_user "DBG: Starting pair for $mac with pin=$pin\n"

spawn bluetoothctl

# Wait for prompt - be generous with timing
expect {
    -re ".*>" { send_user "DBG: Got prompt\n" }
    -re ".*#" { send_user "DBG: Got # prompt\n" }
    timeout { send_user "DBG: Timeout waiting for initial prompt\n"; exit 1 }
}

send "power on\r"
sleep 1

send "agent on\r"
expect {
    "Agent registered" { send_user "DBG: Agent registered\n" }
    "already registered" { send_user "DBG: Agent already registered\n" }
    -re ".*>" { }
    timeout { send_user "DBG: agent on timeout\n" }
}

send "default-agent\r"
expect {
    "Default agent" { send_user "DBG: Default agent set\n" }
    -re ".*>" { }
    timeout { }
}
sleep 0.5

send "pair $mac\r"
send_user "DBG: Sent pair command\n"

# Now wait for various pairing prompts
set timeout 45
expect {
    -re "\\\[agent\\\] PIN code: (\[0-9\]+)" {
        # System generated PIN - user must type this on the keyboard
        set passkey $expect_out(1,string)
        send_user "DBG: System generated PIN: $passkey\n"
        puts "PASSKEY_REQUIRED:$passkey"
        flush stdout
        set timeout 120
        exp_continue
    }
    -re "Passkey: (\[0-9\]+)" {
        set passkey $expect_out(1,string)
        send_user "DBG: Got Passkey: $passkey\n"
        puts "PASSKEY_REQUIRED:$passkey"
        flush stdout
        set timeout 120
        exp_continue
    }
    -re "Confirm passkey (\[0-9\]+)" {
        set passkey $expect_out(1,string)
        send_user "DBG: Got Confirm passkey: $passkey\n"
        puts "PASSKEY_REQUIRED:$passkey"
        flush stdout
        send "yes\r"
        set timeout 120
        exp_continue
    }
    "Request PIN code" {
        send_user "DBG: Got Request PIN code\n"
        if {$pin ne ""} {
            send "$pin\r"
            puts "PASSKEY_REQUIRED:$pin"
        } else {
            send "0000\r"
            puts "PASSKEY_REQUIRED:0000"
        }
        flush stdout
        set timeout 120
        exp_continue
    }
    "Enter PIN code" {
        send_user "DBG: Got Enter PIN code\n"
        if {$pin ne ""} {
            send "$pin\r"
            puts "PASSKEY_REQUIRED:$pin"
        } else {
            send "0000\r"
            puts "PASSKEY_REQUIRED:0000"
        }
        flush stdout
        set timeout 120
        exp_continue
    }
    "Request passkey" {
        send_user "DBG: Got Request passkey\n"
        send "123456\r"
        puts "PASSKEY_REQUIRED:123456"
        flush stdout
        set timeout 120
        exp_continue
    }
    "Pairing successful" {
        send_user "DBG: Pairing successful!\n"
        puts "PAIRING_SUCCESS"
        flush stdout
    }
    "Failed to pair" {
        send_user "DBG: Failed to pair\n"
        puts "PAIRING_FAILED"
        flush stdout
        send "quit\r"
        exit 1
    }
    "not available" {
        send_user "DBG: Device not available\n"
        puts "DEVICE_NOT_AVAILABLE"
        flush stdout
        send "quit\r"
        exit 1
    }
    "Already Exists" {
        send_user "DBG: Already paired\n"
        puts "PAIRING_SUCCESS"
        flush stdout
    }
    timeout {
        send_user "DBG: Timeout during pairing\n"
        puts "PAIRING_TIMEOUT"
        flush stdout
        send "quit\r"
        exit 1
    }
}

# Trust and connect
sleep 0.5
send "trust $mac\r"
expect {
    "trust succeeded" { send_user "DBG: Trust succeeded\n" }
    "Changing" { send_user "DBG: Trust changing\n" }
    -re ".*>" { }
    timeout { }
}

sleep 0.5
send "connect $mac\r"
expect {
    "Connection successful" { send_user "DBG: Connected\n" }
    "Failed to connect" { send_user "DBG: Connect failed (may be OK for keyboards)\n" }
    -re ".*>" { }
    timeout { }
}

send "quit\r"
expect eof
EXPECTSCRIPT
        chmod +x /tmp/bt_pair.exp

        # Run the expect script
        if [ -n "$PIN" ]; then
            /tmp/bt_pair.exp "$MAC" "$PIN" 2>&1
        else
            /tmp/bt_pair.exp "$MAC" "" 2>&1
        fi

        echo "Pairing complete"
        ;;
    remove)
        # $2 = MAC address
        echo "Removing device $2..."
        timeout 5 bash -c "echo 'remove $2' | bluetoothctl" 2>&1
        echo "Device removed"
        ;;
    devices)
        timeout 5 bluetoothctl devices 2>&1
        ;;
    paired_devices)
        # Use 'devices Paired' for newer bluetoothctl, fallback to 'paired-devices' for older
        output=$(echo "devices Paired" | timeout 5 bluetoothctl 2>&1)
        # Extract just the Device lines
        echo "$output" | grep "^Device "
        ;;
    *)
        echo "Usage: $0 {power_on|power_off|scan_on|scan_off|pair|remove|devices|paired_devices}"
        exit 1
        ;;
esac

exit 0
