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
        # Start scan in background with longer timeout
        (echo "scan on"; sleep 15) | bluetoothctl > /dev/null 2>&1 &
        echo "Scan started"
        ;;
    scan_off)
        echo "Stopping Bluetooth scan..."
        timeout 2 bash -c "echo 'scan off' | bluetoothctl" 2>&1
        echo "Scan stopped"
        ;;
    pair)
        # $2 = MAC address, $3 = PIN (optional)
        echo "Pairing with device $2..." >> /tmp/bt_pair_debug.log
        
        # Force scan off
        timeout 2 bash -c "echo 'scan off' | bluetoothctl" >> /tmp/bt_pair_debug.log 2>&1
        
        # Force remove 
        echo "Removing device to ensure fresh state..." >> /tmp/bt_pair_debug.log
        timeout 5 bash -c "echo 'remove $2' | bluetoothctl" >> /tmp/bt_pair_debug.log 2>&1
        sleep 2
        
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
            # Use EXPECT to capture passkey
            expect -c "
                log_file -a /tmp/bt_pair_debug.log
                set timeout 45
                spawn bluetoothctl
                
                # Match any prompt ending in # or > (handling ANSI codes and prefixes)
                expect -re \".*[#>] \"
                send \"agent on\r\"
                expect -re \".*[#>] \"
                send \"default-agent\r\"
                expect -re \".*[#>] \"
                send \"pair $2\r\"
                expect {
                    -re \"Passkey: ([0-9]+)\" {
                        set passkey \$expect_out(1,string)
                        puts \"PASSKEY_REQUIRED:\$passkey\"
                        send_user \"DBG: Matched Passkey: \$passkey\n\"
                        
                        # Now wait for success (user typing PIN)
                        set timeout 120
                        expect {
                            \"Pairing successful\" {
                                send_user \"DBG: Pairing successful after Passkey\n\"
                                send \"trust $2\r\"
                                expect -re \".*[#>] \"
                                send \"connect $2\r\"
                            }
                            timeout {
                                send_user \"DBG: Timeout waiting for PIN entry\n\"
                                exit 1
                            }
                        }
                    }
                    \"Enter PIN code:\" {
                        send_user \"DBG: Matched Enter PIN code\n\"
                        set passkey \"123456\"
                        send \"\$passkey\r\"
                        puts \"PASSKEY_REQUIRED:\$passkey\"
                        
                        set timeout 120
                        expect {
                            \"Pairing successful\" {
                                send_user \"DBG: Pairing successful after PIN\n\"
                                send \"trust $2\r\"
                                expect -re \".*[#>] \"
                                send \"connect $2\r\"
                            }
                            timeout {
                                send_user \"DBG: Timeout waiting for PIN entry\n\"
                                exit 1
                            }
                        }
                    }
                    \"Pairing successful\" {
                         send_user \"DBG: Matched Immediate Pairing successful\n\"
                         send \"trust $2\r\"
                         expect -re \".*[#>] \"
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
                expect -re \".*[#>] \"
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
