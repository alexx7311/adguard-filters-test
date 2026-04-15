#!/bin/bash
# Remove devConfig.json so AG Mini uses default settings.
# Usage: ./remove_devconfig.sh

set -euo pipefail

DEVCONFIG_TARGET="/Library/Application Support/AdGuard Software/com.adguard.safari.AdGuard/devConfig.json"

if [[ ! -f "$DEVCONFIG_TARGET" ]]; then
    echo "devConfig not found — already clean."
    exit 0
fi

echo "Removing: $DEVCONFIG_TARGET"
sudo rm "$DEVCONFIG_TARGET"
echo "Done. Restart AG Mini to apply default settings."
