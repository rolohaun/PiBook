#!/bin/bash
# Safe Git Pull Script for PiBook
# Automatically handles conflicts with user-modifiable files

cd /home/pi/PiBook

echo "Starting safe update..."

# List of files that can be safely overwritten
OVERWRITE_FILES=(
    "scripts/bluetooth_helper.sh"
    "scripts/undervolt_helper.sh"
    "scripts/boot_cores_helper.sh"
)

# Backup settings.json if it exists
if [ -f "settings.json" ]; then
    echo "Backing up settings.json..."
    cp settings.json settings.json.backup
fi

# Reset any modified helper scripts
for file in "${OVERWRITE_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "Resetting $file..."
        git checkout "$file" 2>/dev/null || true
    fi
done

# Pull latest changes
echo "Pulling latest code..."
git pull

# Restore settings.json if backup exists
if [ -f "settings.json.backup" ]; then
    echo "Restoring settings.json..."
    mv settings.json.backup settings.json
fi

# Make scripts executable
echo "Setting script permissions..."
chmod +x scripts/*.sh 2>/dev/null || true

echo "Update complete!"
echo ""
echo "Note: Your settings.json was preserved."
echo "Helper scripts were updated to latest version."
