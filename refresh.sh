#!/bin/bash
# Pulls any new Garmin data and rebuilds dashboard.html.
set -e
cd "$(dirname "$0")"
python3 pull.py
python3 build.py
open dashboard.html
