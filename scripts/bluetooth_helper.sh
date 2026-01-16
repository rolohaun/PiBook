#!/bin/bash
# Bluetooth Helper Script for PiBook
# Provides sudo access for Bluetooth operations

# Enable error output
set -e

case "$1" in
    power_on)
        echo "Powering on Bluetooth..."
        bluetoothctl power on 2>&1
        echo "Bluetooth powered on"
        ;;
    power_off)
        echo "Powering off Bluetooth..."
        bluetoothctl power off 2>&1
        echo "Bluetooth powered off"
        ;;
    scan_on)
        echo "Starting Bluetooth scan..."
        timeout 1 bluetoothctl scan on 2>&1 &
        echo "Scan started"
        ;;
    scan_off)
        echo "Stopping Bluetooth scan..."
        bluetoothctl scan off 2>&1
        echo "Scan stopped"
        ;;
    pair)
        # $2 = MAC address, $3 = PIN (optional)
        echo "Pairing with device $2..."
        if [ -n "$3" ]; then
            # Pairing with PIN using expect
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
            # Pairing without PIN
            echo "agent on" | bluetoothctl
            echo "default-agent" | bluetoothctl
            echo "pair $2" | bluetoothctl
            echo "trust $2" | bluetoothctl
            echo "connect $2" | bluetoothctl
        fi
        echo "Pairing complete"
        ;;
    remove)
        # $2 = MAC address
        echo "Removing device $2..."
        bluetoothctl remove "$2" 2>&1
        echo "Device removed"
        ;;
    devices)
        bluetoothctl devices 2>&1
        ;;
    paired_devices)
        bluetoothctl paired-devices 2>&1
        ;;
    *)
        echo "Usage: $0 {power_on|power_off|scan_on|scan_off|pair|remove|devices|paired_devices}"
        exit 1
        ;;
esac

exit 0
