#!/bin/bash
# Build LiderBPO-Rater - Executável standalone com Chromium embutido

set -e
cd "$(dirname "$0")"

# Caminho do playwright no venv
PLAYWRIGHT_PATH="../../.venv/lib/python3.13/site-packages/playwright"

# Verifica se browsers estão instalados no pacote
if [ ! -d "$PLAYWRIGHT_PATH/driver/package/.local-browsers" ]; then
    echo "Installing Chromium inside playwright package..."
    PLAYWRIGHT_BROWSERS_PATH=0 uv run playwright install chromium
fi

echo "Building executable with bundled Chromium..."

uv run pyinstaller \
    --onefile \
    --windowed \
    --add-data "assets:assets" \
    --add-data "$PLAYWRIGHT_PATH/driver:playwright/driver" \
    --hidden-import playwright \
    --hidden-import playwright.sync_api \
    --name "LiderBPO-Rater" \
    rating_lider.py

echo ""
echo "Build complete: dist/LiderBPO-Rater"
echo "O executável inclui Chromium embutido - nao precisa de instalacao adicional!"
