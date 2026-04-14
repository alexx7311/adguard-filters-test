#!/usr/bin/env python3
"""
Prepare AG Mini database for filter update test cases.

Usage:
  python3 prepare_db.py tc10090 --source <db_path>
  python3 prepare_db.py tc10091 --source <backup_path>
  python3 prepare_db.py tc10277 --source <backup_path>

TC 10090: Sets up for diff update (next_check_time in past)
TC 10091: Sets up for full update (next_check_time in future, blocking diff)
TC 10277: Same as TC 10090 backup state (diff + full sequenced)

The script NEVER modifies the source DB — always works on copies.
"""

import argparse
import hashlib
import base64
import os
import shutil
import sqlite3
import sys
import time
from datetime import datetime, timezone

FILTER_ID = 2
GITHUB_RAW_BASE = "https://raw.githubusercontent.com/alexx7311/adguard-filters-test/main"
DOWNLOAD_URL = f"{GITHUB_RAW_BASE}/extension/safari/filters/2_optimized.txt"
FIRST_PATCH_RELATIVE = "../patches/2_optimized/2_optimized-s-1700003600-3600.patch"

# Path to the base filter content (v1.0.0) relative to this script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_FILTER_PATH = os.path.join(SCRIPT_DIR, "..", "base", "2_optimized_v1.0.0.txt")


def compute_filter_checksum(content: str) -> str:
    """Compute ! Checksum: value (base64-no-pad MD5, excluding checksum line)."""
    lines = content.split("\n")
    content_lines = []
    for line in lines:
        trimmed = line.strip()
        if trimmed.startswith("! Checksum:"):
            continue
        content_lines.append(trimmed)
    joined = "\n".join(content_lines)
    md5_digest = hashlib.md5(joined.encode("utf-8")).digest()
    return base64.b64encode(md5_digest).decode("ascii").rstrip("=")


def count_rules(content: str) -> int:
    """Count rule lines (non-empty, non-comment, non-metadata)."""
    count = 0
    for line in content.split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.startswith("!"):
            continue
        count += 1
    return count


def read_base_filter() -> str:
    """Read the v1.0.0 filter content."""
    path = BASE_FILTER_PATH
    if not os.path.exists(path):
        print(f"Error: base filter not found at {path}", file=sys.stderr)
        print("Make sure you're running from the repo checkout.", file=sys.stderr)
        sys.exit(1)
    with open(path, "r") as f:
        content = f.read()
    # Remove trailing newline (FLM stores content without trailing newline)
    if content.endswith("\n"):
        content = content[:-1]
    return content


def prepare_tc10090(source_db: str):
    """Prepare DB for TC 10090 (diff update test)."""
    now = int(time.time())
    one_day_ago = now - 86400
    one_hour_ago = now - 3600

    # Read base filter content
    filter_content = read_base_filter()
    checksum = ""
    # Extract checksum from the file itself (more reliable)
    for line in filter_content.split("\n"):
        if line.strip().startswith("! Checksum:"):
            checksum = line.split(": ", 1)[1].strip()
            break
    rules_count = count_rules(filter_content)

    # Create output directory
    output_dir = os.path.join(os.getcwd(), "prepared_dbs")
    os.makedirs(output_dir, exist_ok=True)
    output_db = os.path.join(output_dir, "agflm_tc10090.db")
    backup_db = os.path.join(output_dir, f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")

    # Copy source DB
    shutil.copy2(source_db, output_db)
    print(f"Copied {source_db} -> {output_db}")

    conn = sqlite3.connect(output_db)
    try:
        # Update filter table
        conn.execute("""
            UPDATE filter SET
                version = ?,
                checksum = ?,
                last_download_time = ?,
                is_installed = 1,
                is_enabled = 1,
                download_url = ?,
                subscription_url = ?
            WHERE filter_id = ?
        """, ("1.0.0", checksum, one_day_ago, DOWNLOAD_URL, DOWNLOAD_URL, FILTER_ID))

        # Update rules_list — set text_hash to NULL (safe: FLM never validates before patching)
        conn.execute("""
            UPDATE rules_list SET
                rules_text = ?,
                disabled_rules_text = '',
                rules_count = ?,
                has_directives = 1,
                text_hash = NULL
            WHERE filter_id = ?
        """, (filter_content, rules_count, FILTER_ID))

        # Upsert diff_updates
        conn.execute("DELETE FROM diff_updates WHERE filter_id = ?", (FILTER_ID,))
        conn.execute("""
            INSERT INTO diff_updates (filter_id, next_path, next_check_time)
            VALUES (?, ?, ?)
        """, (FILTER_ID, FIRST_PATCH_RELATIVE, one_hour_ago))

        conn.commit()

        # Verify
        row = conn.execute(
            "SELECT version, download_url, last_download_time FROM filter WHERE filter_id = ?",
            (FILTER_ID,)
        ).fetchone()
        du = conn.execute(
            "SELECT next_path, next_check_time FROM diff_updates WHERE filter_id = ?",
            (FILTER_ID,)
        ).fetchone()
        rl = conn.execute(
            "SELECT rules_count, text_hash FROM rules_list WHERE filter_id = ?",
            (FILTER_ID,)
        ).fetchone()

        print(f"\n=== TC 10090 DB Summary ===")
        print(f"filter.version:          {row[0]}")
        print(f"filter.download_url:     {row[1][:60]}...")
        print(f"filter.last_download_time: {row[2]} ({datetime.fromtimestamp(row[2], tz=timezone.utc).isoformat()})")
        print(f"diff_updates.next_path:  {du[0]}")
        print(f"diff_updates.next_check_time: {du[1]} ({datetime.fromtimestamp(du[1], tz=timezone.utc).isoformat()})")
        print(f"rules_list.rules_count:  {rl[0]}")
        print(f"rules_list.text_hash:    {rl[1]}")
        print(f"\nOutput DB: {output_db}")
    finally:
        conn.close()

    # Create backup
    shutil.copy2(output_db, backup_db)
    print(f"Backup: {backup_db}")
    return output_db, backup_db


def prepare_tc10091(source_db: str):
    """Prepare DB for TC 10091 (full update — diff blocked by future next_check_time)."""
    now = int(time.time())
    one_day_future = now + 86400

    output_dir = os.path.join(os.getcwd(), "prepared_dbs")
    os.makedirs(output_dir, exist_ok=True)
    output_db = os.path.join(output_dir, "agflm_tc10091.db")

    shutil.copy2(source_db, output_db)
    print(f"Copied {source_db} -> {output_db}")

    six_days_ago = now - 6 * 86400

    conn = sqlite3.connect(output_db)
    try:
        # Set last_download_time to 6 days ago so filter is expired (expires=432000=5 days)
        # This ensures full update triggers even if ignore_filters_expiration=false
        conn.execute("""
            UPDATE filter SET last_download_time = ?
            WHERE filter_id = ?
        """, (six_days_ago, FILTER_ID))

        conn.execute("""
            UPDATE diff_updates SET next_check_time = ?
            WHERE filter_id = ?
        """, (one_day_future, FILTER_ID))
        conn.commit()

        row = conn.execute(
            "SELECT last_download_time FROM filter WHERE filter_id = ?",
            (FILTER_ID,)
        ).fetchone()
        du = conn.execute(
            "SELECT next_path, next_check_time FROM diff_updates WHERE filter_id = ?",
            (FILTER_ID,)
        ).fetchone()

        print(f"\n=== TC 10091 DB Summary ===")
        print(f"filter.last_download_time:   {row[0]} ({datetime.fromtimestamp(row[0], tz=timezone.utc).isoformat()})")
        print(f"  (6 days ago: filter is expired, ensures full update)")
        print(f"diff_updates.next_path:      {du[0]}")
        print(f"diff_updates.next_check_time: {du[1]} ({datetime.fromtimestamp(du[1], tz=timezone.utc).isoformat()})")
        print(f"  (in future: diff update blocked -> full update will be used)")
        print(f"\nOutput DB: {output_db}")
    finally:
        conn.close()
    return output_db


def prepare_tc10277(source_db: str):
    """Prepare DB for TC 10277 (same as tc10090 backup state)."""
    output_dir = os.path.join(os.getcwd(), "prepared_dbs")
    os.makedirs(output_dir, exist_ok=True)
    output_db = os.path.join(output_dir, "agflm_tc10277.db")

    shutil.copy2(source_db, output_db)
    print(f"Copied {source_db} -> {output_db}")

    conn = sqlite3.connect(output_db)
    try:
        row = conn.execute(
            "SELECT version, download_url FROM filter WHERE filter_id = ?",
            (FILTER_ID,)
        ).fetchone()
        du = conn.execute(
            "SELECT next_path, next_check_time FROM diff_updates WHERE filter_id = ?",
            (FILTER_ID,)
        ).fetchone()

        print(f"\n=== TC 10277 DB Summary ===")
        print(f"filter.version:          {row[0]}")
        print(f"filter.download_url:     {row[1][:60]}...")
        print(f"diff_updates.next_path:  {du[0]}")
        print(f"diff_updates.next_check_time: {du[1]} ({datetime.fromtimestamp(du[1], tz=timezone.utc).isoformat()})")
        print(f"\nOutput DB: {output_db}")
    finally:
        conn.close()
    return output_db


def main():
    parser = argparse.ArgumentParser(description="Prepare AG Mini DB for filter update tests")
    parser.add_argument("tc", choices=["tc10090", "tc10091", "tc10277"],
                        help="Test case to prepare for")
    parser.add_argument("--source", required=True,
                        help="Path to source DB (original for tc10090, backup for tc10091/tc10277)")
    args = parser.parse_args()

    if not os.path.exists(args.source):
        print(f"Error: source DB not found: {args.source}", file=sys.stderr)
        sys.exit(1)

    if args.tc == "tc10090":
        prepare_tc10090(args.source)
    elif args.tc == "tc10091":
        prepare_tc10091(args.source)
    elif args.tc == "tc10277":
        prepare_tc10277(args.source)


if __name__ == "__main__":
    main()
