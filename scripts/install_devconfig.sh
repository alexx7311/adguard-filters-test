#!/bin/bash
# Install devConfig.json for the specified test case.
# Usage: ./install_devconfig.sh <tc_number>
# Example: ./install_devconfig.sh tc10090

set -euo pipefail

DEVCONFIG_TARGET="/Library/Application Support/AdGuard Software/com.adguard.safari.AdGuard/devConfig.json"
DEVCONFIG_TARGET_DIR="$(dirname "$DEVCONFIG_TARGET")"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEVCONFIG_DIR="$SCRIPT_DIR/../devconfig"

TC="${1:-}"
if [[ -z "$TC" ]]; then
    echo "Usage: $0 <tc10090|tc10091|tc10277>"
    echo "  tc10090 - diff update config"
    echo "  tc10091 - full update config"
    echo "  tc10277 - diff + full update config"
    exit 1
fi

SOURCE="$DEVCONFIG_DIR/devconfig_${TC}.json"
if [[ ! -f "$SOURCE" ]]; then
    echo "Error: devconfig file not found: $SOURCE"
    exit 1
fi

echo "=== Installing devConfig for $TC ==="
echo "Source: $SOURCE"
echo "Target: $DEVCONFIG_TARGET"
echo ""

# Show content
echo "Content:"
cat "$SOURCE"
echo ""

# Create target directory if it doesn't exist
if [[ ! -d "$DEVCONFIG_TARGET_DIR" ]]; then
    echo "Creating directory: $DEVCONFIG_TARGET_DIR"
    sudo mkdir -p "$DEVCONFIG_TARGET_DIR"
fi

# Copy and set permissions (requires sudo)
sudo cp "$SOURCE" "$DEVCONFIG_TARGET"
sudo chmod 444 "$DEVCONFIG_TARGET"
sudo chown 0:0 "$DEVCONFIG_TARGET"

echo ""
echo "Installed. Verifying permissions:"
ls -la "$DEVCONFIG_TARGET"
echo ""
echo "Done. Restart AG Mini for the config to take effect."
