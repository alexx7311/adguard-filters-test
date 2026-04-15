#!/bin/bash
# Remove AG Mini filter database so the app recreates it from scratch.
# Usage: ./remove_db.sh

set -euo pipefail

DB_PATH="$HOME/Library/Group Containers/TC3Q7MAJXF.com.adguard.mac/Library/Application Support/com.adguard.safari.AdGuard/Filters/agflm_standard.db"

if [[ ! -f "$DB_PATH" ]]; then
    echo "DB not found — already clean."
    exit 0
fi

echo "Removing: $DB_PATH"
rm "$DB_PATH"
echo "Done. AG Mini will recreate the database on next launch."
