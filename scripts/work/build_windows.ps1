# Build script for Windows (PowerShell)
# Este script deve ser executado em uma máquina Windows para gerar o .exe real.

$PLAYWRIGHT_PATH = "..\..\.venv\Lib\site-packages\playwright"

# Instala o Chromium localmente se necessário
Write-Host "Installing Chromium inside playwright package..."
$env:PLAYWRIGHT_BROWSERS_PATH = "0"
uv run playwright install chromium

Write-Host "Building executable with bundled Chromium..."
uv run pyinstaller `
    --onefile `
    --windowed `
    --add-data "assets;assets" `
    --add-data "$PLAYWRIGHT_PATH\driver;playwright\driver" `
    --hidden-import playwright `
    --hidden-import playwright.sync_api `
    --name "LiderBPO-Rater" `
    rating_lider.py

Write-Host "Build complete: dist\LiderBPO-Rater.exe"
