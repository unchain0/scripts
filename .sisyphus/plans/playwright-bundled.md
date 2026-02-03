# Playwright Bundled - Executável Standalone

## Context

### Original Request

O usuário quer que o executável Windows inclua o Playwright e Chromium embutidos, sem necessidade de instalação pelo usuário final.

### Solution

Usar `PLAYWRIGHT_BROWSERS_PATH=0` para instalar browsers dentro do pacote Playwright, e incluir tudo no PyInstaller.

---

## TODOs

- [x] 1. Atualizar rating_lider.py para usar browsers embutidos

  **What to do**:
  - Adicionar no início do arquivo (ANTES dos imports do Playwright):

    ```python
    # Configura Playwright para usar browsers embutidos no pacote
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "0")
    ```

  - Atualizar docstring com instruções de build

  **Files**: `scripts/work/rating_lider.py`

  **Acceptance Criteria**:
  - [ ] `os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "0")` presente antes do import do Playwright
  - [ ] Testes passam: `uv run pytest tests/test_rating_lider.py -v`

---

- [x] 2. Atualizar build.sh para incluir Playwright e browsers

  **What to do**:
  - Atualizar `scripts/work/build.sh` com:

    ```bash
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
    echo "O executável inclui Chromium embutido - não precisa de instalação adicional!"
    ```

  **Files**: `scripts/work/build.sh`

  **Acceptance Criteria**:
  - [ ] Script inclui `--add-data` para o driver do Playwright
  - [ ] Script verifica e instala browsers se necessário
  - [ ] Comentário indica que não precisa instalação adicional

---

- [x] 3. Commit das alterações

  **What to do**:
  - Commitar: `git add -A && git commit -m "feat(rating_lider): bundle playwright and chromium in executable"`

  **Acceptance Criteria**:
  - [ ] Commit criado com as alterações

---

## Success Criteria

- [x] `uv run pytest tests/test_rating_lider.py -v` → 23 tests pass
- [x] `PLAYWRIGHT_BROWSERS_PATH=0` configurado antes do import
- [x] build.sh inclui o driver do Playwright no executável
- [x] Usuário final NÃO precisa rodar `playwright install`
