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
        echo "Pairing with device $2..." >> /tmp/bt_pair_debug.log

        # NOTE: Do NOT force lock/remove here. It causes "Device not available" error.
        # We assume the user has just scanned and the device is known to BlueZ.
        # Attempts to clean up state aggressively are backfiring.

        if [ -n "$3" ]; then
            # Pairing with USER-PROVIDED PIN (legacy/simple devices)
            expect -c "
                set timeout 30
                spawn bluetoothctl
                expect \"#\"
                send \"agent on\r\"
                expect \"#\"
                send \"default-agent\r\"
                expect \"#\"
                send \"pair $2\r\"
                expect {
                    \"Enter PIN code:\" {
                        send \"$3\r\"
                        expect \"#\"
                    }
                    \"Pairing successful\" {
                        # No PIN needed
                    }
                    timeout {
                        send \"quit\r\"
                        exit 1
                    }
                }
                send \"trust $2\r\"
                expect \"#\"
                send \"connect $2\r\"
                expect \"#\"
                send \"quit\r\"
            " 2>&1
        else
            # Pairing WITHOUT user-provided PIN (might generate Passkey)
            # Use EXPECT to capture passkey - handles Apple keyboards and similar devices
            # For legacy keyboards (A1255 etc), BlueZ generates a PIN that user types on keyboard

            # First remove any existing pairing to force fresh pairing
            echo "Removing existing pairing for $2..." >> /tmp/bt_pair_debug.log
            timeout 3 bash -c "echo -e 'remove $2\nquit' | bluetoothctl" 2>/dev/null || true
            sleep 1

            expect -c "
                log_file -a /tmp/bt_pair_debug.log
                set timeout 45
                spawn bluetoothctl

                # Match any prompt ending in # or > (handling ANSI codes and prefixes)
                # Use braces {} for regex to prevent Tcl command substitution on []
                expect -re {.*[#>]}
                send \"power on\r\"
                expect -re {.*[#>]}
                # Use KeyboardDisplay agent - this forces PIN/passkey prompts
                send \"agent KeyboardDisplay\r\"
                expect -re {.*[#>]}
                send \"default-agent\r\"
                expect -re {.*[#>]}
                send \"pair $2\r\"
                expect {
                    -re {Passkey: ([0-9]+)} {
                        # Modern device showing passkey for user to type
                        set passkey \$expect_out(1,string)
                        puts \"PASSKEY_REQUIRED:\$passkey\"
                        flush stdout
                        send_user \"DBG: Matched Passkey: \$passkey\n\"

                        # Now wait for success (user typing PIN on device)
                        set timeout 120
                        expect {
                            \"Pairing successful\" {
                                send_user \"DBG: Pairing successful after Passkey\n\"
                                send \"trust $2\r\"
                                expect -re {.*[#>]}
                                send \"connect $2\r\"
                            }
                            timeout {
                                send_user \"DBG: Timeout waiting for PIN entry\n\"
                                exit 1
                            }
                        }
                    }
                    -re {Confirm passkey ([0-9]+)} {
                        # SSP passkey confirmation - user types code on keyboard
                        set passkey \$expect_out(1,string)
                        puts \"PASSKEY_REQUIRED:\$passkey\"
                        flush stdout
                        send_user \"DBG: Matched Confirm passkey: \$passkey\n\"

                        # Auto-confirm on our side
                        send \"yes\r\"

                        # Wait for pairing to complete (user types code on keyboard)
                        set timeout 120
                        expect {
                            \"Pairing successful\" {
                                send_user \"DBG: Pairing successful after Confirm passkey\n\"
                                send \"trust $2\r\"
                                expect -re {.*[#>]}
                                send \"connect $2\r\"
                            }
                            timeout {
                                send_user \"DBG: Timeout waiting for user to type passkey\n\"
                                exit 1
                            }
                        }
                    }
                    -re {Request passkey|Enter passkey} {
                        # Device requesting a passkey - generate one for user to type on keyboard
                        send_user \"DBG: Matched Request/Enter passkey\n\"
                        set passkey \"123456\"
                        send \"\$passkey\r\"
                        puts \"PASSKEY_REQUIRED:\$passkey\"
                        flush stdout

                        set timeout 120
                        expect {
                            \"Pairing successful\" {
                                send_user \"DBG: Pairing successful after passkey entry\n\"
                                send \"trust $2\r\"
                                expect -re {.*[#>]}
                                send \"connect $2\r\"
                            }
                            timeout {
                                send_user \"DBG: Timeout waiting for passkey entry\n\"
                                exit 1
                            }
                        }
                    }
                    -re {Request PIN code|Enter PIN code} {
                        # Legacy PIN pairing - generate PIN for user to type on keyboard
                        send_user \"DBG: Matched Request/Enter PIN code\n\"
                        set passkey \"0000\"
                        send \"\$passkey\r\"
                        puts \"PASSKEY_REQUIRED:\$passkey\"
                        flush stdout

                        set timeout 120
                        expect {
                            \"Pairing successful\" {
                                send_user \"DBG: Pairing successful after PIN\n\"
                                send \"trust $2\r\"
                                expect -re {.*[#>]}
                                send \"connect $2\r\"
                            }
                            timeout {
                                send_user \"DBG: Timeout waiting for PIN entry\n\"
                                exit 1
                            }
                        }
                    }
                    -re {Attempting to pair|Pairing successful} {
                         # Immediate pairing without PIN/passkey
                         send_user \"DBG: Matched Attempting/Pairing - no PIN required\n\"
                         # Check if it was just \"Attempting\" - wait for result
                         expect {
                             \"Pairing successful\" {
                                 send_user \"DBG: Pairing completed successfully\n\"
                             }
                             \"Failed to pair\" {
                                 send_user \"DBG: Pairing failed\n\"
                                 exit 1
                             }
                             timeout {
                                 send_user \"DBG: Pairing timeout\n\"
                             }
                         }
                         send \"trust $2\r\"
                         expect -re {.*[#>]}
                         send \"connect $2\r\"
                         expect {
                             \"Connection successful\" {
                                 send_user \"DBG: Connection successful\n\"
                             }
                             \"Failed to connect\" {
                                 send_user \"DBG: Failed to connect\n\"
                             }
                             timeout {
                                 send_user \"DBG: Timeout waiting for connection\n\"
                             }
                         }
                    }
                    timeout {
                         send_user \"DBG: Timeout waiting for pair response\n\"
                         send \"quit\r\"
                         exit 1
                    }
                }
                expect -re {.*[#>]}
                send \"quit\r\"
            " 2>&1
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
        timeout 5 bluetoothctl paired-devices 2>&1
        ;;
    *)
        echo "Usage: $0 {power_on|power_off|scan_on|scan_off|pair|remove|devices|paired_devices}"
        exit 1
        ;;
esac

exit 0
