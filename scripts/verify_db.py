#!/usr/bin/env python3
"""
Post-test verification: read AG Mini database and print filter_id=2 state.

Usage:
  python3 verify_db.py                    # uses default AG Mini DB path
  python3 verify_db.py --db <path>        # uses custom path
"""

import argparse
import os
import sqlite3
import sys
from datetime import datetime, timezone

DEFAULT_DB_PATH = os.path.expanduser(
    "~/Library/Group Containers/TC3Q7MAJXF.com.adguard.mac/"
    "Library/Application Support/com.adguard.safari.AdGuard/"
    "Filters/agflm_standard.db"
)

FILTER_ID = 2


def fmt_ts(epoch):
    """Format epoch timestamp to human-readable."""
    if epoch is None:
        return "NULL"
    try:
        dt = datetime.fromtimestamp(epoch, tz=timezone.utc)
        return f"{epoch} ({dt.strftime('%Y-%m-%d %H:%M:%S UTC')})"
    except (ValueError, OSError):
        return f"{epoch} (invalid)"


def main():
    parser = argparse.ArgumentParser(description="Verify AG Mini DB state for filter_id=2")
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="Path to agflm_standard.db")
    args = parser.parse_args()

    if not os.path.exists(args.db):
        print(f"Error: DB not found: {args.db}", file=sys.stderr)
        sys.exit(1)

    conn = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    try:
        # Filter table
        row = conn.execute("""
            SELECT version, checksum, last_download_time, last_update_time,
                   is_installed, is_enabled, download_url, expires
            FROM filter WHERE filter_id = ?
        """, (FILTER_ID,)).fetchone()

        if row is None:
            print(f"filter_id={FILTER_ID} not found in filter table!", file=sys.stderr)
            sys.exit(1)

        print(f"=== Filter ID {FILTER_ID} ===")
        print(f"  version:            {row[0]}")
        print(f"  checksum:           {row[1]}")
        print(f"  last_download_time: {fmt_ts(row[2])}")
        print(f"  last_update_time:   {fmt_ts(row[3])}")
        print(f"  is_installed:       {row[4]}")
        print(f"  is_enabled:         {row[5]}")
        print(f"  download_url:       {row[6]}")
        print(f"  expires:            {row[7]}")

        # diff_updates table
        du = conn.execute("""
            SELECT next_path, next_check_time
            FROM diff_updates WHERE filter_id = ?
        """, (FILTER_ID,)).fetchone()

        print(f"\n=== Diff Updates ===")
        if du:
            print(f"  next_path:          {du[0]}")
            print(f"  next_check_time:    {fmt_ts(du[1])}")
        else:
            print("  (no diff_updates entry)")

        # rules_list table
        rl = conn.execute("""
            SELECT rules_count, text_hash, length(rules_text) as text_len
            FROM rules_list WHERE filter_id = ?
        """, (FILTER_ID,)).fetchone()

        print(f"\n=== Rules List ===")
        if rl:
            print(f"  rules_count:        {rl[0]}")
            th = rl[1] if rl[1] else "NULL"
            if th and len(th) > 16:
                th = th[:16] + "..."
            print(f"  text_hash:          {th}")
            print(f"  rules_text length:  {rl[2]} bytes")
        else:
            print("  (no rules_list entry)")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
