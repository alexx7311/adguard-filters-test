# AdGuard Filters Update Test Infrastructure

Test filter + diff patches for semi-automated verification of AG Mini filter update test cases (TC 10090, 10091, 10277).

## Repository Structure

```
extension/safari/
  filters.json                              # Metadata (1 test filter, version 1.0.49)
  filters/2_optimized.txt                   # Latest filter (v1.0.49, for full downloads)
  patches/2_optimized/                      # 49 RCS diff patches + 1 terminal (0 bytes)
base/
  2_optimized_v1.0.0.txt                    # Base filter (v1.0.0, for DB injection)
devconfig/
  devconfig_tc10090.json                    # diff update config
  devconfig_tc10091.json                    # full update config
  devconfig_tc10277.json                    # diff + full config
scripts/
  prepare_db.py                             # DB preparation for each TC
  install_devconfig.sh                      # devConfig installer (macOS)
  verify_db.py                              # Post-test DB state viewer
```

## Prerequisites

- macOS with AG Mini (AdGuard for Safari) installed
- Python 3 (stdlib only — no extra packages)
- Proxyman or Charles for network monitoring
- `sudo` access for devConfig installation

## AG Mini DB Path

```
~/Library/Group Containers/TC3Q7MAJXF.com.adguard.mac/Library/Application Support/com.adguard.safari.AdGuard/Filters/agflm_standard.db
```

## TC 10090 — Diff Update

Tests that AG Mini applies diff patches (incremental update).

```bash
# 1. Quit AG Mini

# 2. Install devConfig
./scripts/install_devconfig.sh tc10090

# 3. Prepare DB (copies source, never modifies original)
python3 scripts/prepare_db.py tc10090 --source <path_to_agflm_standard.db>
# Copy the output DB to the AG Mini DB path

# 4. Open Proxyman, start recording

# 5. Launch AG Mini, enable AdGuard Base Filter in settings

# 6. Wait ~60 seconds for diff update cycle

# 7. Verify in Proxyman:
#    - Requests to raw.githubusercontent.com for patch files
#    - NO request for 2_optimized.txt (full filter)

# 8. Verify DB state
python3 scripts/verify_db.py
# Expected: version changed from 1.0.0 to 1.0.49
```

## TC 10091 — Full Update

Tests that AG Mini performs a full filter download (not diff).

```bash
# 1. Quit AG Mini

# 2. Install devConfig
./scripts/install_devconfig.sh tc10091

# 3. Prepare DB (use the backup from TC 10090)
python3 scripts/prepare_db.py tc10091 --source prepared_dbs/backup_*.db
# Copy the output DB to the AG Mini DB path

# 4. Open Proxyman, start recording

# 5. Launch AG Mini

# 6. Wait ~60 seconds for full update cycle

# 7. Verify in Proxyman:
#    - Request for 2_optimized.txt (full filter download)
#    - NO requests for patch files

# 8. Verify DB state
python3 scripts/verify_db.py
# Expected: version = 1.0.49, rules_text length matches latest filter
```

## TC 10277 — Diff Update Followed by Full Update

Tests both update types in sequence.

```bash
# 1. Quit AG Mini

# 2. Install devConfig
./scripts/install_devconfig.sh tc10277

# 3. Prepare DB (use the backup from TC 10090)
python3 scripts/prepare_db.py tc10277 --source prepared_dbs/backup_*.db
# Copy the output DB to the AG Mini DB path

# 4. Open Proxyman, start recording

# 5. Launch AG Mini

# 6. Wait for diff update (~60s), then full update (~90s)

# 7. Verify in Proxyman:
#    - First: requests for patch files (diff update)
#    - Then: request for 2_optimized.txt (full update)

# 8. Verify DB state
python3 scripts/verify_db.py
```

## How It Works

- `filters_meta_url` in devConfig redirects AG Mini's metadata fetch to this GitHub repo
- `prepare_db.py` sets filter version to 1.0.0 and `download_url` to this repo's raw URL
- FLM resolves patch paths relative to `download_url`, so all patches are fetched from GitHub
- The filter chain: v1.0.0 → 49 diff patches → v1.0.49 (terminal empty patch signals "no more updates")

## Important Notes

- `pull_metadata` will remove other standard filters from the DB (our filters.json only has filter 2)
- `text_hash` is set to NULL in prepared DBs (safe: FLM doesn't validate it before patching)
- Assumption: `filters_full_update_period` in devConfig triggers `update_filters(ignore_filters_expiration=true)` in AG Mini
