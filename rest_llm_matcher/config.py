"""
Configuration for GAME Matcher Service

- Determines if running inside a container or not
- Automatically versions the Matcher name using Apptainer's build-date label.
- Inside container:             "Matcher_20251128-180629_TZ"  (sortable, human-readable)
- Outside container (Dev mode): "Matcher_dev"
"""

import os
import json
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

MODULE_NAME = "Matcher"
GAME_SCHEMA_VERSION = "1.0"

if os.path.exists('/.singularity.d'):
    print("Running inside the container...")
    try:
        with open('/.singularity.d/labels.json', 'r') as f:
            labels = json.load(f)
        raw_build_date = labels.get('org.label-schema.build-date', '')
        parts = raw_build_date.split('_')
        date_str = f"{parts[1]}_{parts[2]}_{parts[3]}_{parts[4]}"
        dt = datetime.strptime(date_str, "%d_%B_%Y_%H:%M:%S")
        build_timestamp = dt.strftime("%Y%m%d-%H%M%S")
        timezone_label = parts[5] if len(parts) > 5 else "UNK"
        MATCHER_NAME = f"{MODULE_NAME}_{build_timestamp}_{timezone_label}"
    except Exception as e:
        print(f"Warning: Could not parse build timestamp from labels.json: {e}")
        MATCHER_NAME = f"{MODULE_NAME}_unknown"
else:
    print("Running outside the container (dev mode)...")
    MATCHER_NAME = f"{MODULE_NAME}_dev"