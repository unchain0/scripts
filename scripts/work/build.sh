#!/bin/bash
# Build LiderBPO-Rater executable for Windows
# Prerequisites: playwright install chromium (run on target machine)

cd "$(dirname "$0")"

uv run pyinstaller \
    --onefile \
    --windowed \
    --add-data "assets:assets" \
    --name "LiderBPO-Rater" \
    rating_lider.py

echo "Build complete: dist/LiderBPO-Rater"
echo "Note: User must run 'playwright install chromium' before using the executable"
