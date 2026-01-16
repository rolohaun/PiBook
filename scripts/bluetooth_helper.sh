#!/bin/bash
# Bluetooth Helper Script for PiBook
# Provides sudo access for Bluetooth operations

case "$1" in
    power_on)
        bluetoothctl power on
        ;;
    power_off)
        bluetoothctl power off
        ;;
    scan_on)
        bluetoothctl scan on &
        ;;
    scan_off)
        bluetoothctl scan off
        ;;
    pair)
        # $2 = MAC address, $3 = PIN (optional)
        if [ -n "$3" ]; then
            # Pairing with PIN using expect
            expect -c "
                spawn bluetoothctl
                expect \"#\"
                send \"agent on\r\"
                expect \"#\"
                send \"default-agent\r\"
                expect \"#\"
                send \"pair $2\r\"
                expect \"Enter PIN code:\"
                send \"$3\r\"
                expect \"#\"
                send \"trust $2\r\"
                expect \"#\"
                send \"connect $2\r\"
                expect \"#\"
                send \"quit\r\"
            "
        else
            # Pairing without PIN
            bluetoothctl pair "$2"
            bluetoothctl trust "$2"
            bluetoothctl connect "$2"
        fi
        ;;
    remove)
        # $2 = MAC address
        bluetoothctl remove "$2"
        ;;
    devices)
        bluetoothctl devices
        ;;
    paired_devices)
        bluetoothctl paired-devices
        ;;
    *)
        echo "Usage: $0 {power_on|power_off|scan_on|scan_off|pair|remove|devices|paired_devices}"
        exit 1
        ;;
esac
