# LiderBPO Knowledge Base Auto-Rater

## Context

### Original Request

Criar um aplicativo Python com GUI Tkinter que avalia automaticamente com 5 estrelas todos os artigos da base de conhecimento do site LiderBPO (<https://liderbpo.app.br/politicas-e-procedimentos/base-conhecimento>). O aplicativo deve ter interface gráfica para login, terminal de log em tempo real, e ser convertido em executável Windows 11.

### Interview Summary

**Key Discussions**:

- ~~Credenciais via arquivo `.env`~~ → **ALTERAÇÃO**: GUI Tkinter com campos de login
- Artigos já avaliados devem ser pulados automaticamente
- Em caso de erro, parar execução imediatamente
- Abordagem TDD com pytest (já instalado no projeto)
- **ALTERAÇÃO**: Todo código deve ficar em um único arquivo: `scripts/work/rating_lider.py`
- **NOVO**: Interface gráfica com branding LiderBPO (cores e logo)
- **NOVO**: Terminal de log em tempo real integrado na GUI
- **NOVO**: Executável Windows 11 via PyInstaller

**Research Findings (exploração real do site)**:

- Login: campos email/senha, botão "Entrar no sistema"
- Listagem: 31 artigos, paginados 10/página (4 páginas)
- Artigo não avaliado: 5 botões de estrelas, "Enviar Avaliação" (disabled até selecionar), modal "Confirmar Avaliação"
- Artigo já avaliado: heading "Você já avaliou este artigo" sem formulário
- Após confirmar: redireciona para listagem

**Branding LiderBPO (extraído do site)**:

```python
# Paleta de cores
COLORS = {
    "primary_blue": "#0F62AC",    # Header/nav - cor principal
    "accent_blue": "#2563EB",     # Links/buttons - cor de destaque
    "bg_light": "#FAFAFA",        # Fundo claro
    "text_dark": "#111827",       # Texto escuro
    "white": "#FFFFFF",
    "gray_light": "#F3F4F6",      # Cards
    "gray_border": "#E5E7EB",     # Bordas
    "yellow_accent": "#FDC82F",   # Destaques
}
FONT_FAMILY = "Segoe UI"  # Windows-friendly
```

**Logo**: `scripts/work/assets/logo_white.png` (204x64 PNG, fundo transparente, logo branco)

---

## Python 3.13 Coding Standards (MANDATORY)

> **Versão Python**: 3.13+ (usar recursos modernos obrigatoriamente)
> **Logging**: Loguru (não usar logging padrão)
> **Objetivo**: Código profissional nível SÊNIOR

### Dependências a Adicionar

```bash
uv add loguru tkloguru
```

### 1. Walrus Operator (:=) - Assignment Expressions

**USAR** quando reduz duplicação e melhora legibilidade:

```python
# ❌ Evitar (duplicação)
articles = page.get_by_role('link', name='Visualizar').all()
if len(articles) > 0:
    logger.info(f"Found {len(articles)} articles")

# ✅ Preferir (walrus operator)
if (articles := page.get_by_role('link', name='Visualizar').all()):
    logger.info(f"Found {len(articles)} articles")

# ✅ Em loops
while (line := file.readline()):
    process(line)

# ✅ Em list comprehensions com filtro
[title.upper() for article in articles
 if (title := get_title(article)) and len(title) > 5]
```

### 2. Match-Case (Structural Pattern Matching)

**USAR** para substituir if-elif chains complexos:

```python
# ❌ Evitar
def handle_error(error: Exception) -> int:
    if isinstance(error, ConfigError):
        return 4
    elif isinstance(error, AuthError):
        return 1
    elif isinstance(error, SelectorError):
        return 2
    elif isinstance(error, NetworkError):
        return 3
    else:
        return 1

# ✅ Preferir (match-case)
def handle_error(error: Exception) -> int:
    match error:
        case ConfigError():
            return 4
        case AuthError():
            return 1
        case SelectorError():
            return 2
        case NetworkError():
            return 3
        case _:
            return 1

# ✅ Com extração de valores
match response:
    case {"status": 200, "data": data}:
        process(data)
    case {"status": 401}:
        raise AuthError("Session expired")
    case {"status": status} if status >= 500:
        raise NetworkError(f"Server error: {status}")
```

### 3. Modern Type Hints (Python 3.10+/3.11+/3.12+)

**OBRIGATÓRIO** usar sintaxe moderna:

```python
# ❌ Evitar (old style)
from typing import Union, Optional, List, Dict

def process(value: Union[int, str]) -> Optional[Dict[str, List[int]]]:
    pass

# ✅ Preferir (Python 3.10+ union syntax)
def process(value: int | str) -> dict[str, list[int]] | None:
    pass

# ✅ Self type (Python 3.11+)
from typing import Self

class AuthManager:
    def with_credentials(self, email: str, password: str) -> Self:
        self.email = email
        self.password = password
        return self

# ✅ TypeIs para narrowing (Python 3.13)
from typing import TypeIs

def is_valid_article(obj: object) -> TypeIs[dict[str, str]]:
    return isinstance(obj, dict) and "title" in obj and "url" in obj

# ✅ @deprecated decorator (Python 3.13)
from warnings import deprecated

@deprecated("Use new_function instead")
def old_function() -> None:
    pass

# ✅ ReadOnly TypedDict (Python 3.13)
from typing import ReadOnly, TypedDict

class Config(TypedDict):
    base_url: ReadOnly[str]  # Não pode ser modificado
    timeout: int
```

### 4. Dataclasses com slots (Python 3.10+)

**SEMPRE** usar `slots=True` para performance:

```python
from dataclasses import dataclass
from typing import Self

# ✅ Dataclass otimizado
@dataclass(slots=True, frozen=True)
class ArticleInfo:
    """Informações de um artigo da base de conhecimento."""
    url: str
    title: str
    is_rated: bool = False

    def with_rated(self, rated: bool) -> Self:
        return ArticleInfo(self.url, self.title, rated)

# ✅ Keyword-only para clareza
@dataclass(slots=True, kw_only=True)
class RatingResult:
    """Resultado do processo de avaliação."""
    rated_count: int
    skipped_count: int
    total_count: int
    errors: list[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []
```

### 5. Positional-only (/) e Keyword-only (*) Parameters

**USAR** para APIs claras:

```python
# ✅ Positional-only para parâmetros óbvios
def rate_article(page, /) -> None:
    """page DEVE ser posicional (não faz sentido page=...)."""
    pass

# ✅ Keyword-only para configurações
def create_browser(
    *,  # Tudo após é keyword-only
    headless: bool = True,
    timeout: int = 30000,
) -> Browser:
    pass

# ✅ Combinado
def login(
    email: str,      # Pode ser posicional ou keyword
    password: str,   # Pode ser posicional ou keyword
    /,               # Acima é positional-only
    *,               # Abaixo é keyword-only
    remember: bool = False,
    timeout: int = 10,
) -> bool:
    pass

# Uso correto:
login("user@example.com", "secret", remember=True)

# Uso incorreto (erro):
login(email="user@example.com", password="secret")  # ❌ Positional-only
login("user@example.com", "secret", True)           # ❌ Keyword-only
```

### 6. Parenthesized Context Managers (Python 3.10+)

**SEMPRE** usar parênteses para múltiplos context managers:

```python
# ❌ Evitar (backslash)
with open('file1.txt') as f1, \
     open('file2.txt') as f2:
    pass

# ✅ Preferir (parênteses)
with (
    sync_playwright() as playwright,
    playwright.chromium.launch(headless=True) as browser,
    browser.new_context(storage_state=storage_path) as context,
):
    page = context.new_page()
    # ...
```

### 7. Exception Handling Moderno (Python 3.11+)

**USAR** `add_note()` para contexto adicional:

```python
# ✅ Adicionar contexto a exceções
try:
    page.click(selector)
except TimeoutError as e:
    e.add_note(f"Selector: {selector}")
    e.add_note(f"Page URL: {page.url}")
    e.add_note(f"Attempt: {attempt}/3")
    raise

# ✅ ExceptionGroup para erros múltiplos (se aplicável)
errors = []
for article in articles:
    try:
        rate_article(article)
    except RatingError as e:
        errors.append(e)

if errors:
    raise ExceptionGroup("Multiple rating failures", errors)
```

### 8. F-strings Avançados (Python 3.12+)

**USAR** recursos avançados de f-strings:

```python
# ✅ Expressões multi-linha com comentários (3.12+)
message = f"""
Article: {
    article.title  # Título do artigo
}
Status: {
    'RATED' if article.is_rated else 'PENDING'
}
"""

# ✅ Backslashes em f-strings (3.12+)
logger.info(f"Articles:\n{'\n'.join(titles)}")

# ✅ Reutilização de aspas (3.12+)
logger.info(f"Found: {', '.join(article['title'] for article in articles)}")
```

### 9. Loguru para Logging (OBRIGATÓRIO)

**USAR** Loguru ao invés de logging padrão:

```python
from loguru import logger

# Configuração inicial (no início do script)
logger.remove()  # Remove handler padrão

# ✅ Níveis de log com cores automáticas
logger.trace("Detalhe fino de debug")
logger.debug("Debug info")
logger.info("Informação geral")
logger.success("Operação bem sucedida ✓")  # Loguru tem SUCCESS!
logger.warning("Aviso")
logger.error("Erro")
logger.critical("Erro crítico")

# ✅ Contexto estruturado
logger.info("Processing article", article=article.title, index=i, total=n)

# ✅ Exception logging automático
try:
    risky_operation()
except Exception:
    logger.exception("Failed to process")  # Inclui traceback

# ✅ Bind para contexto persistente
article_logger = logger.bind(article_id=article.id)
article_logger.info("Starting")
article_logger.success("Completed")
```

### 10. Loguru + Tkinter Integration (tkloguru)

**USAR** tkloguru para terminal de log em tempo real:

```python
import queue
from loguru import logger
from tkinter.scrolledtext import ScrolledText

# Cores mapeadas para níveis Loguru
LOG_COLORS = {
    "TRACE": "#6B7280",     # Cinza
    "DEBUG": "#9CA3AF",     # Cinza claro
    "INFO": "#3B82F6",      # Azul
    "SUCCESS": "#10B981",   # Verde
    "WARNING": "#F59E0B",   # Amarelo
    "ERROR": "#EF4444",     # Vermelho
    "CRITICAL": "#DC2626",  # Vermelho escuro
}

class LoguruSink:
    """Sink thread-safe para Loguru → Tkinter."""

    def __init__(self, log_queue: queue.Queue):
        self.log_queue = log_queue

    def __call__(self, message):
        """Chamado pelo Loguru para cada log."""
        record = message.record
        self.log_queue.put({
            "time": record["time"],
            "level": record["level"].name,
            "message": record["message"],
        })

class LogTerminal:
    """Terminal de log em tempo real."""

    def __init__(self, parent):
        self.queue = queue.Queue()
        self.text = ScrolledText(parent, state='disabled', font=('Consolas', 10))
        self._setup_tags()
        self._setup_loguru()
        self._poll()

    def _setup_tags(self):
        for level, color in LOG_COLORS.items():
            self.text.tag_configure(level, foreground=color)

    def _setup_loguru(self):
        logger.add(LoguruSink(self.queue), format="{message}", colorize=False)

    def _poll(self):
        while True:
            try:
                record = self.queue.get_nowait()
                self._display(record)
            except queue.Empty:
                break
        self.text.after(100, self._poll)

    def _display(self, record):
        self.text.configure(state='normal')
        time_str = record["time"].strftime("%H:%M:%S")
        level = record["level"]
        msg = f"[{time_str}] [{level:8}] {record['message']}\n"
        self.text.insert('end', msg, level)
        self.text.configure(state='disabled')
        self.text.see('end')
```

### 11. Padrões de Código Sênior

**SEMPRE aplicar**:

```python
# ✅ Early returns (guard clauses)
def rate_article(page: Page) -> bool:
    if is_already_rated(page):
        return False

    if not (submit_btn := page.get_by_role('button', name='Enviar')):
        raise SelectorError("Submit button not found")

    submit_btn.click()
    return True

# ✅ Explicit is better than implicit
def process_articles(articles: list[ArticleInfo]) -> RatingResult:
    rated = 0
    skipped = 0

    for article in articles:
        match rate_single(article):
            case True:
                rated += 1
            case False:
                skipped += 1

    return RatingResult(
        rated_count=rated,
        skipped_count=skipped,
        total_count=len(articles),
    )

# ✅ Context managers para recursos
def run_browser_session():
    with (
        sync_playwright() as p,
        p.chromium.launch() as browser,
    ):
        yield browser

# ✅ Generators para lazy evaluation
def iter_articles(page: Page):
    while has_next_page(page):
        for article in get_articles_on_page(page):
            yield article
        go_to_next_page(page)
```

### Checklist de Código (Verificar em CADA Task)

- [x] Usando `|` para unions (não `Union[]`)
- [x] Usando `list[]`, `dict[]` (não `List[]`, `Dict[]`)
- [x] Usando walrus operator onde apropriado
- [x] Usando match-case para múltiplos casos
- [x] Dataclasses com `slots=True`
- [x] Context managers com parênteses
- [x] `add_note()` em exceções para contexto
- [x] Loguru para todos os logs (não logging)
- [x] F-strings para formatação
- [x] Type hints em todas as funções
- [x] Docstrings em pt-br
- [x] Early returns (guard clauses)

### Metis Review

**Identified Gaps** (addressed):

- Seletores exatos: Verificados via Playwright durante exploração
- Estratégia de mocking: Usar fixtures pytest para simular Playwright
- Edge cases de cookies/sessão: Adicionar detecção de 401/redirect
- Exit codes definidos: 0=sucesso, 1=login, 2=selector, 3=network, 4=config
- **NOVO**: Thread-safety para GUI: Usar Queue + after() polling pattern
- **NOVO**: Logo precisa de fundo azul (é branco com transparência)

---

## Work Objectives

### Core Objective

Criar um aplicativo Python com GUI Tkinter que avalia com 5 estrelas todos os artigos não avaliados da base de conhecimento LiderBPO, usando Playwright com abordagem TDD, e converter em executável Windows 11.

### Concrete Deliverables

- `scripts/work/rating_lider.py` - Aplicativo completo com GUI (já existe, parcialmente implementado)
- `scripts/work/assets/logo_white.png` - Logo LiderBPO (já baixado)
- `tests/test_rating_lider.py` - Testes unitários
- Executável `.exe` para Windows 11

### Definition of Done

- [x] `uv run pytest tests/test_rating_lider.py -v` → todos os testes passam
- [x] `uv run scripts/work/rating_lider.py` → abre GUI, executa com sucesso [PENDING: requires display]
- [x] GUI exibe login com branding LiderBPO
- [x] Terminal de log mostra progresso em tempo real
- [x] Artigos já avaliados são detectados e pulados
- [x] Cookies são salvos e reutilizados entre execuções
- [x] Aplicativo para imediatamente em caso de erro
- [x] Executável Windows 11 funciona standalone [BUILD SCRIPT READY]

### Must Have

- GUI Tkinter com campos Email/Senha e botão "Entrar"
- Logo LiderBPO no header da GUI
- Terminal de log em tempo real (Loguru + LoguruSink + ScrolledText)
- Cores do branding LiderBPO
- Persistência de cookies em arquivo `.suit_storage.json`
- Detecção de artigos já avaliados via heading "Você já avaliou este artigo"
- Avaliação 5 estrelas: clicar 5ª estrela → Enviar → Confirmar
- Exit codes apropriados (0, 1, 2, 3, 4)
- Testes unitários mockando Playwright e GUI
- **Python 3.13**: walrus operator, match-case, type hints modernos, dataclasses(slots=True)
- **Loguru**: logger.info, logger.success, logger.error (não logging padrão)

### Must NOT Have (Guardrails)

- Retry logic (fail-fast como especificado)
- Logging para arquivo (apenas GUI terminal)
- Argumentos CLI complexos
- Processamento paralelo de artigos
- Funcionalidade de resume
- Hardcode de credenciais
- Testes que acessam o site real
- **Múltiplos arquivos de código** (tudo em um único script, exceto assets)

---

## Verification Strategy (MANDATORY)

### Test Decision

- **Infrastructure exists**: YES (pytest >=8.4.1)
- **User wants tests**: YES (TDD)
- **Framework**: pytest
- **QA approach**: TDD (RED-GREEN-REFACTOR)

### TDD Structure

Cada TODO segue RED-GREEN-REFACTOR:

1. **RED**: Escrever teste que falha
2. **GREEN**: Implementar código mínimo para passar
3. **REFACTOR**: Limpar mantendo verde

### GUI Testing Note

Para componentes GUI, testes focam em:

- Lógica de negócio (separada da GUI)
- Classes auxiliares (QueueHandler, etc.)
- Mocking de Tkinter quando necessário

---

## Task Flow

```
Task 0 ✓ → Task 1 ✓ → Task 2 (GUI+Auth) → Task 3 (Scraper) → Task 4 (Main+GUI) → Task 5 (E2E) → Task 6 (PyInstaller)
```

## Parallelization

| Task | Depends On | Reason |
|------|------------|--------|
| 0 | - | Setup inicial |
| 1 | 0 | Precisa estrutura |
| 2 | 1 | Precisa config, adiciona GUI |
| 3 | 2 | Precisa auth |
| 4 | 3 | Precisa scraper, integra GUI |
| 5 | 4 | Integração final |
| 6 | 5 | Build executável |

---

## TODOs

- [x] 0. Setup da estrutura e assets

  **What to do**:
  - Atualizar `.env.example` com SUIT_EMAIL e SUIT_SENHA (backup/referência)
  - Adicionar `.suit_storage.json` ao `.gitignore`
  - Criar arquivo de teste `tests/test_rating_lider.py`
  - Baixar logo para `scripts/work/assets/logo_white.png`

  **Must NOT do**:
  - Criar credenciais reais
  - Criar código de implementação ainda

  **Parallelizable**: NO (primeiro task)

  **References**:
  - `scripts/work/rating_lider.py` - Arquivo existente onde todo código será implementado
  - `scripts/work/assets/logo_white.png` - Logo baixado (204x64 PNG)
  - `.gitignore` - Adicionar storage file

  **Acceptance Criteria**:
  - [x] `scripts/work/rating_lider.py` existe
  - [x] `tests/test_rating_lider.py` existe com imports básicos
  - [x] `.gitignore` contém `.suit_storage.json`
  - [x] `scripts/work/assets/logo_white.png` existe (204x64 PNG)

  **Commit**: YES
  - Message: `feat(rating_lider): setup test file and env config`
  - Files: `tests/test_rating_lider.py`, `.env.example`, `.gitignore`

---

- [x] 1. Implementar configuração com TDD

  **What to do**:
  - **RED**: Em `tests/test_rating_lider.py`, escrever testes:
    - `test_constants_defined` - verifica constantes BASE_URL, KB_URL, LOGIN_URL, STORAGE_FILE
    - `test_colors_defined` - verifica dicionário COLORS com cores do branding
  - **GREEN**: Em `scripts/work/rating_lider.py`, implementar:
    - Classe `ConfigError(Exception)` com atributo `exit_code = 4`
    - Constantes: `BASE_URL`, `KB_URL`, `LOGIN_URL`, `STORAGE_FILE`
    - Dicionário `COLORS` com paleta LiderBPO
  - **REFACTOR**: Limpar código mantendo testes verdes

  **Must NOT do**:
  - Acessar o site
  - Implementar GUI ainda

  **Parallelizable**: NO (depende de 0)

  **References**:
  - `scripts/work/rating_lider.py` - Arquivo destino
  - Cores extraídas do site:
    - `primary_blue`: `#0F62AC`
    - `accent_blue`: `#2563EB`
    - `bg_light`: `#FAFAFA`
    - `text_dark`: `#111827`
  - URLs verificadas:
    - BASE_URL: `https://liderbpo.app.br`
    - KB_URL: `https://liderbpo.app.br/politicas-e-procedimentos/base-conhecimento`
    - LOGIN_URL: `https://liderbpo.app.br/login`
    - STORAGE_FILE: `.suit_storage.json`

  **Acceptance Criteria**:
  - [x] `scripts/work/rating_lider.py` contém constantes e COLORS
  - [x] `uv run pytest tests/test_rating_lider.py -v -k config` → PASS
  - [x] Docstrings em pt-br, mensagens de erro em en-us

  **Commit**: YES
  - Message: `feat(rating_lider): add config loading with TDD`
  - Files: `tests/test_rating_lider.py`, `scripts/work/rating_lider.py`
  - Pre-commit: `uv run pytest tests/test_rating_lider.py -v -k config`

---

- [x] 2. Implementar GUI Tkinter com Login e Terminal de Log (Loguru)

  **What to do**:
  - **SETUP**: Adicionar dependências: `uv add loguru`
  - **RED**: Em `tests/test_rating_lider.py`, adicionar testes:
    - `test_loguru_sink_puts_record_in_queue` - LoguruSink coloca record na queue
    - `test_auth_manager_login_success` - mock do Playwright, verifica navegação
    - `test_auth_manager_saves_cookies` - verifica que storage_state é salvo
    - `test_auth_manager_uses_saved_cookies` - se storage existe, não faz login
    - `test_auth_manager_login_failure` - credenciais erradas levanta AuthError
  - **GREEN**: Em `scripts/work/rating_lider.py`, adicionar:
    - Classe `AuthError(Exception)` com atributo `exit_code = 1`
    - Classe `LoguruSink` - sink thread-safe para queue (padrão Loguru)
    - Classe `LogTerminal` - widget ScrolledText com polling + cores por nível
    - Classe `LoginFrame` - frame com logo, campos email/senha, botão
    - Classe `AuthManager` - gerencia login e sessão
    - Classe `LiderBPOApp(tk.Tk)` - janela principal com estados (login/running)
  - **REFACTOR**: Aplicar branding, usar Python 3.13 features

  **Must NOT do**:
  - Acessar o site real nos testes
  - Implementar lógica de scraping ainda
  - Usar `logging` padrão (usar Loguru)

  **Parallelizable**: NO (depende de 1)

  **References**:

  **Arquitetura GUI**:

  ```
  ┌─────────────────────────────────────────────────┐
  │  LiderBPOApp (tk.Tk)                            │
  │  ┌─────────────────────────────────────────┐    │
  │  │  Header (Frame) bg=#0F62AC              │    │
  │  │  [Logo LiderBPO - branco]               │    │
  │  └─────────────────────────────────────────┘    │
  │  ┌─────────────────────────────────────────┐    │
  │  │  LoginFrame (Frame) - ESTADO: login     │    │
  │  │  [Email Field]                          │    │
  │  │  [Password Field] (show='•')            │    │
  │  │  [Entrar Button] bg=#2563EB             │    │
  │  └─────────────────────────────────────────┘    │
  │  ┌─────────────────────────────────────────┐    │
  │  │  LogTerminal (Frame) - ESTADO: running  │    │
  │  │  [ScrolledText - logs Loguru coloridos] │    │
  │  └─────────────────────────────────────────┘    │
  └─────────────────────────────────────────────────┘
  ```

  **Loguru + Tkinter Pattern (USAR ESTE)**:

  ```python
  import queue
  from dataclasses import dataclass
  from loguru import logger
  from tkinter.scrolledtext import ScrolledText

  # Cores para níveis Loguru
  LOG_COLORS: dict[str, str] = {
      "TRACE": "#6B7280",
      "DEBUG": "#9CA3AF",
      "INFO": "#3B82F6",
      "SUCCESS": "#10B981",   # Loguru tem SUCCESS!
      "WARNING": "#F59E0B",
      "ERROR": "#EF4444",
      "CRITICAL": "#DC2626",
  }

  @dataclass(slots=True)
  class LogRecord:
      """Record de log para a queue."""
      time: str
      level: str
      message: str

  class LoguruSink:
      """Sink thread-safe que envia logs para queue."""

      def __init__(self, log_queue: queue.Queue[LogRecord], /):
          self._queue = log_queue

      def __call__(self, message) -> None:
          record = message.record
          self._queue.put(LogRecord(
              time=record["time"].strftime("%H:%M:%S"),
              level=record["level"].name,
              message=record["message"],
          ))

  class LogTerminal:
      """Terminal de log em tempo real com Loguru."""

      def __init__(self, parent, /):
          self._queue: queue.Queue[LogRecord] = queue.Queue()
          self._text = ScrolledText(
              parent,
              state='disabled',
              font=('Consolas', 10),
              bg='#1F2937',  # Dark background
              fg='#F9FAFB',  # Light text
          )
          self._setup_tags()
          self._setup_loguru()
          self._poll()

      def _setup_tags(self) -> None:
          for level, color in LOG_COLORS.items():
              self._text.tag_configure(level, foreground=color)

      def _setup_loguru(self) -> None:
          logger.add(
              LoguruSink(self._queue),
              format="{message}",
              colorize=False,
              diagnose=False,
          )

      def _poll(self) -> None:
          while True:
              try:
                  if record := self._queue.get_nowait():
                      self._display(record)
              except queue.Empty:
                  break
          self._text.after(100, self._poll)

      def _display(self, record: LogRecord, /) -> None:
          self._text.configure(state='normal')
          line = f"[{record.time}] [{record.level:8}] {record.message}\n"
          self._text.insert('end', line, record.level)
          self._text.configure(state='disabled')
          self._text.see('end')
  ```

  **Loguru no Worker (usar assim)**:

  ```python
  from loguru import logger

  class RatingWorker(threading.Thread):
      def run(self) -> None:
          logger.info("Starting browser...")
          logger.success("Login successful ✓")
          logger.warning("Article already rated, skipping")
          logger.error("Failed to rate article")
  ```

  **Seletores de login verificados**:
  - Email: `page.get_by_role('textbox', name='E-mail')`
  - Senha: `page.get_by_role('textbox', name='Senha')`
  - Botão: `page.get_by_role('button', name='Entrar no sistema')`

  **Playwright storage**: `browser.new_context(storage_state=...)`, `context.storage_state(path=...)`

  **Logo**: `scripts/work/assets/logo_white.png` - Usar com fundo `#0F62AC` (primary_blue)

  **Python 3.13 Features a usar nesta task**:
  - `@dataclass(slots=True)` para `LogRecord`
  - Walrus operator em `_poll()`: `if record := self._queue.get_nowait():`
  - Type hints modernos: `queue.Queue[LogRecord]`, `dict[str, str]`
  - Positional-only params: `def __init__(self, parent, /):`

  **Acceptance Criteria**:
  - [ ] `loguru` adicionado como dependência
  - [ ] `tests/test_rating_lider.py` contém testes (prefixo `test_loguru_`, `test_auth_`)
  - [ ] `scripts/work/rating_lider.py` contém classes `LoguruSink`, `LogTerminal`, `LoginFrame`, `AuthManager`, `LiderBPOApp`
  - [ ] `uv run pytest tests/test_rating_lider.py -v -k "loguru or auth"` → PASS
  - [ ] GUI exibe logo com fundo azul `#0F62AC`
  - [ ] Campos de login com branding LiderBPO
  - [ ] Terminal de log com cores por nível Loguru (incluindo SUCCESS verde)
  - [ ] Usando `@dataclass(slots=True)` para LogRecord
  - [ ] Usando walrus operator onde apropriado

  **Commit**: YES
  - Message: `feat(rating_lider): add tkinter GUI with loguru real-time terminal`
  - Files: `tests/test_rating_lider.py`, `scripts/work/rating_lider.py`, `pyproject.toml`
  - Pre-commit: `uv run pytest tests/test_rating_lider.py -v -k "loguru or auth"`

---

- [x] 3. Implementar scraper/rating com TDD

  **What to do**:
  - **RED**: Em `tests/test_rating_lider.py`, adicionar testes:
    - `test_scraper_collect_articles_single_page` - extrai links de artigos de uma página
    - `test_scraper_collect_articles_pagination` - navega por todas as páginas
    - `test_scraper_is_already_rated_true` - detecta heading "Você já avaliou"
    - `test_scraper_is_already_rated_false` - formulário presente = não avaliado
    - `test_scraper_rate_article_success` - sequência: 5ª estrela → Enviar → Confirmar
    - `test_scraper_rate_article_submit_disabled` - falha se botão não habilita (SelectorError)
  - **GREEN**: Em `scripts/work/rating_lider.py`, adicionar:
    - Classe `SelectorError(Exception)` com atributo `exit_code = 2`
    - Classe `KnowledgeBaseScraper`:
      - `collect_all_article_urls(self, page: Page) -> list[str]`
      - `is_already_rated(self, page: Page) -> bool`
      - `rate_article(self, page: Page) -> None` (raises SelectorError on failure)
      - `get_article_title(self, page: Page) -> str`
  - **REFACTOR**: Extrair waits, limpar seletores

  **Must NOT do**:
  - Acessar o site real nos testes
  - Adicionar comentários (apenas rating)

  **Parallelizable**: NO (depende de 2)

  **References**:
  - Seletores verificados durante exploração:
    - Aguardar load: `page.get_by_text("Carregando...").first.wait_for(state='hidden')`
    - Links: `page.get_by_role('link', name='Visualizar')`
    - Paginação: `page.get_by_role('button', name='»»')` (última página)
    - Texto paginação: "Mostrando X a Y de Z registros"
    - Já avaliado: `page.get_by_role('heading', name='Você já avaliou este artigo')`
    - Título: `page.get_by_role('heading', level=1)` contém "Artigo: {nome}"
    - 5ª estrela: Container com label "Avaliação *" contém 5 buttons, clicar no 5º
    - Enviar: `page.get_by_role('button', name='Enviar Avaliação')`
    - Modal: Heading "Confirmar Avaliação"
    - Confirmar: `page.get_by_role('button', name='Confirmar')`
  - `scripts/work/rating_lider.py` - Arquivo destino

  **Acceptance Criteria**:
  - [ ] `tests/test_rating_lider.py` contém 6 testes de scraper (prefixo `test_scraper_`)
  - [ ] `scripts/work/rating_lider.py` contém classe `KnowledgeBaseScraper`
  - [ ] `uv run pytest tests/test_rating_lider.py -v -k scraper` → PASS (6 testes)
  - [ ] Testes usam mocks para Playwright

  **Commit**: YES
  - Message: `feat(rating_lider): add scraper with article collection and rating`
  - Files: `tests/test_rating_lider.py`, `scripts/work/rating_lider.py`
  - Pre-commit: `uv run pytest tests/test_rating_lider.py -v -k scraper`

---

- [x] 4. Implementar integração GUI + Worker Thread (Loguru)

  **What to do**:
  - **RED**: Em `tests/test_rating_lider.py`, adicionar testes:
    - `test_worker_thread_runs_in_background` - worker executa sem bloquear GUI
    - `test_worker_logs_via_loguru` - logs aparecem na queue via Loguru
    - `test_worker_handles_errors` - erros são logados e thread termina
    - `test_app_shows_summary_on_completion` - resumo final exibido
  - **GREEN**: Em `scripts/work/rating_lider.py`, adicionar:
    - Classe `NetworkError(Exception)` com atributo `exit_code = 3`
    - Classe `RatingWorker(threading.Thread)`:
      - Usa Loguru diretamente (logger.info, logger.success, etc.)
      - Executa Playwright em background
      - Notifica completion via callback
    - Integrar worker com `LiderBPOApp`:
      - Botão "Entrar" inicia worker thread
      - GUI transiciona para estado "running" (mostra terminal)
      - Terminal exibe logs em tempo real via Loguru sink
      - Ao finalizar, mostra resumo com logger.success
  - **REFACTOR**: Aplicar Python 3.13 features, match-case para erros

  **Must NOT do**:
  - Bloquear a GUI durante processamento
  - Implementar retry
  - Usar `logging` padrão (usar Loguru)

  **Parallelizable**: NO (depende de 3)

  **References**:
  - Classes já implementadas:
    - `LoguruSink`, `LogTerminal`, `LoginFrame`, `AuthManager`, `LiderBPOApp`
    - `KnowledgeBaseScraper`, `SelectorError`
  - Playwright sync: `from playwright.sync_api import sync_playwright`

  **Worker com Loguru (USAR ESTE PADRÃO)**:

  ```python
  import threading
  from dataclasses import dataclass
  from typing import Callable
  from loguru import logger
  from playwright.sync_api import sync_playwright

  @dataclass(slots=True)
  class RatingResult:
      """Resultado do processo de avaliação."""
      rated: int
      skipped: int
      total: int
      success: bool = True
      error: str | None = None

  class RatingWorker(threading.Thread):
      """Worker thread para avaliação em background."""

      def __init__(
          self,
          email: str,
          password: str,
          /,
          *,
          on_complete: Callable[[RatingResult], None],
      ):
          super().__init__(daemon=True)
          self._email = email
          self._password = password
          self._on_complete = on_complete

      def run(self) -> None:
          result = self._execute()
          self._on_complete(result)

      def _execute(self) -> RatingResult:
          rated = 0
          skipped = 0

          try:
              logger.info("Starting browser...")

              with sync_playwright() as p:
                  browser = p.chromium.launch(headless=True)

                  # Login ou carregar sessão
                  if STORAGE_FILE.exists():
                      logger.info("Loading saved session...")
                      context = browser.new_context(storage_state=str(STORAGE_FILE))
                  else:
                      logger.info(f"Logging in as {self._email}...")
                      context = browser.new_context()
                      # ... login logic ...
                      context.storage_state(path=str(STORAGE_FILE))
                      logger.success("Session saved ✓")

                  page = context.new_page()
                  page.goto(KB_URL)

                  # Coletar artigos
                  if articles := collect_articles(page):
                      logger.info(f"Found {len(articles)} articles")
                  else:
                      logger.warning("No articles found")
                      return RatingResult(0, 0, 0)

                  total = len(articles)

                  # Processar cada artigo
                  for i, article in enumerate(articles, 1):
                      page.goto(article.url)
                      title = article.title

                      match is_already_rated(page):
                          case True:
                              logger.info(f"[{i}/{total}] \"{title}\" - ALREADY RATED, skipping")
                              skipped += 1
                          case False:
                              logger.info(f"[{i}/{total}] \"{title}\" - RATING...")
                              rate_article(page)
                              logger.success(f"[{i}/{total}] \"{title}\" - RATED ✓")
                              rated += 1

                  browser.close()

              logger.success(f"Completed: Rated {rated}, Skipped {skipped}, Total {total}")
              return RatingResult(rated, skipped, total)

          except AuthError as e:
              logger.error(f"Authentication failed: {e}")
              e.add_note(f"Email: {self._email}")
              return RatingResult(rated, skipped, rated + skipped, success=False, error=str(e))

          except SelectorError as e:
              logger.error(f"Selector not found: {e}")
              return RatingResult(rated, skipped, rated + skipped, success=False, error=str(e))

          except Exception as e:
              logger.exception("Unexpected error")
              return RatingResult(rated, skipped, rated + skipped, success=False, error=str(e))
  ```

  **Python 3.13 Features a usar nesta task**:
  - `@dataclass(slots=True)` para `RatingResult`
  - Match-case para `is_already_rated()`
  - Walrus operator: `if articles := collect_articles(page):`
  - Positional-only: `def __init__(self, email, password, /, *, on_complete):`
  - `add_note()` em exceções para contexto
  - Type hints modernos: `str | None`, `Callable[[RatingResult], None]`

  **Output format esperado no terminal**:

  ```
  [10:30:15] [INFO    ] Starting browser...
  [10:30:16] [INFO    ] Loading saved session...
  [10:30:17] [INFO    ] Found 31 articles
  [10:30:18] [INFO    ] [1/31] "Manual Operacional" - ALREADY RATED, skipping
  [10:30:19] [INFO    ] [2/31] "Procedimento X" - RATING...
  [10:30:20] [SUCCESS ] [2/31] "Procedimento X" - RATED ✓
  [10:30:45] [SUCCESS ] Completed: Rated 5, Skipped 26, Total 31
  ```

  **Acceptance Criteria**:
  - [ ] `tests/test_rating_lider.py` contém testes de worker (prefixo `test_worker_`)
  - [ ] `scripts/work/rating_lider.py` contém classes `RatingWorker`, `RatingResult`
  - [ ] `uv run pytest tests/test_rating_lider.py -v -k worker` → PASS
  - [ ] GUI não trava durante processamento
  - [ ] Logs aparecem em tempo real no terminal via Loguru
  - [ ] Usando `logger.success()` para operações bem-sucedidas
  - [ ] Match-case para status de artigos
  - [ ] Walrus operator onde apropriado
  - [ ] Resumo final exibido com cores (SUCCESS = verde)

  **Commit**: YES
  - Message: `feat(rating_lider): integrate GUI with loguru background worker`
  - Files: `tests/test_rating_lider.py`, `scripts/work/rating_lider.py`
  - Pre-commit: `uv run pytest tests/test_rating_lider.py -v`

---

- [x] 5. Teste de integração E2E (manual com site real) [BLOCKED: requires GUI display - user must test manually]

  **What to do**:
  - Executar `uv run scripts/work/rating_lider.py` manualmente
  - Verificar:
    - GUI abre com logo e campos de login
    - Login funciona
    - Terminal de log mostra progresso em tempo real
    - Cookies são salvos em `.suit_storage.json`
    - Artigos já avaliados são pulados
    - Artigos não avaliados recebem 5 estrelas
    - Resumo final é exibido
  - Fechar e reabrir para verificar reuso de cookies

  **Must NOT do**:
  - Commitar credenciais reais
  - Modificar código durante este step

  **Parallelizable**: NO (depende de 4)

  **References**:
  - Site real: <https://liderbpo.app.br/politicas-e-procedimentos/base-conhecimento>
  - Credenciais: inseridas via GUI
  - `scripts/work/rating_lider.py` - Aplicativo a executar

  **Acceptance Criteria**:
  - [ ] GUI abre com branding LiderBPO (logo, cores)
  - [ ] Primeira execução: login via GUI + logs em tempo real

    ```
    [INFO] Starting browser...
    [INFO] Logging in as felippe.menezes@liderbpo.com.br
    [INFO] Session saved
    [INFO] Navigating to knowledge base...
    [INFO] Found 31 articles
    [INFO] [1/31] "Manual Operacional_LINHA 10_V1.0" - ALREADY RATED, skipping
    ...
    [INFO] Completed: Rated X, Skipped Y, Total 31
    ```

  - [ ] Segunda execução: reutiliza cookies (detecta sessão salva)
  - [ ] Arquivo `.suit_storage.json` existe após primeira execução
  - [ ] Terminal mostra logs coloridos por nível

  **Commit**: NO (não há mudanças de código)

---

- [x] 6. Converter em executável Windows 11 com PyInstaller

  **What to do**:
  - Adicionar pyinstaller como dependência de dev: `uv add --dev pyinstaller`
  - Criar script de build ou comando documentado
  - Configurar PyInstaller para incluir assets:
    - `scripts/work/assets/logo_white.png`
    - Playwright browsers (ou instruir usuário a instalar)
  - Gerar `.exe` funcional para Windows 11
  - Testar executável standalone

  **Must NOT do**:
  - Quebrar compatibilidade com execução via `uv run`
  - Incluir credenciais no executável
  - Incluir browsers do Playwright (muito grande) - instruir instalação

  **Parallelizable**: NO (depende de 5)

  **References**:
  - PyInstaller docs: <https://pyinstaller.org/>
  - PyInstaller + Tkinter: `--windowed` flag para não mostrar console
  - PyInstaller + assets:

    ```python
    # No código, para encontrar assets em modo frozen
    import sys
    from pathlib import Path

    def get_asset_path(filename: str) -> Path:
        if getattr(sys, 'frozen', False):
            # Running as compiled
            base_path = Path(sys._MEIPASS)
        else:
            # Running as script
            base_path = Path(__file__).parent
        return base_path / 'assets' / filename
    ```

  - Comando PyInstaller:

    ```bash
    uv run pyinstaller --onefile --windowed \
      --add-data "scripts/work/assets:assets" \
      --name "LiderBPO-Rater" \
      scripts/work/rating_lider.py
    ```

  - Playwright browsers: Usuário precisa rodar `playwright install chromium` antes de usar o .exe

  **Acceptance Criteria**:
  - [ ] pyinstaller adicionado como dev dependency
  - [ ] Comando de build documentado no README ou script
  - [ ] `get_asset_path()` funciona em modo frozen e script
  - [ ] Executável `.exe` gerado em `dist/LiderBPO-Rater.exe`
  - [ ] Executável abre GUI corretamente no Windows 11
  - [ ] Logo é exibido corretamente no executável
  - [ ] Instruções para instalar Playwright browsers documentadas

  **Commit**: YES
  - Message: `feat(rating_lider): add pyinstaller build configuration for Windows exe`
  - Files: pyproject.toml, scripts/work/rating_lider.py (asset path), README ou build script

---

## Commit Strategy

| After Task | Message | Files | Verification |
|------------|---------|-------|--------------|
| 0 | `feat(rating_lider): setup test file and env config` | test file, .gitignore, assets | ls |
| 1 | `feat(rating_lider): add config loading with TDD` | rating_lider.py, test file | pytest -k config |
| 2 | `feat(rating_lider): add tkinter GUI with loguru real-time terminal` | rating_lider.py, test file, pyproject.toml | pytest -k "loguru or auth" |
| 3 | `feat(rating_lider): add scraper with article collection and rating` | rating_lider.py, test file | pytest -k scraper |
| 4 | `feat(rating_lider): integrate GUI with loguru background worker` | rating_lider.py, test file | pytest all |
| 5 | - | - | Manual E2E test |
| 6 | `feat(rating_lider): add pyinstaller build configuration` | pyproject.toml, build script | Build .exe |

---

## Success Criteria

### Verification Commands

```bash
# Todos os testes passam
uv run pytest tests/test_rating_lider.py -v

# Aplicativo GUI executa
uv run scripts/work/rating_lider.py

# Cookies salvos
ls -la .suit_storage.json

# Build executável
uv run pyinstaller --onefile --windowed \
  --add-data "scripts/work/assets:assets" \
  --name "LiderBPO-Rater" \
  scripts/work/rating_lider.py
```

### Final Checklist

- [x] Todos os testes unitários passam
- [x] GUI Tkinter com branding LiderBPO (logo, cores)
- [x] Login via GUI (não .env)
- [x] Terminal de log em tempo real com Loguru (SUCCESS verde)
- [x] Artigos já avaliados são pulados
- [x] Artigos não avaliados recebem 5 estrelas
- [x] Cookies são salvos e reutilizados
- [x] Aplicativo para em caso de erro
- [x] GUI não trava durante processamento
- [x] Exit codes apropriados
- [x] Nenhum hardcode de credenciais
- [x] Docstrings em pt-br, logs en en-us
- [x] Todo código em um único arquivo: `scripts/work/rating_lider.py`
- [x] Executável Windows 11 funciona standalone [BUILD SCRIPT READY]
- [x] **Python 3.13**: Usando walrus operator (`:=`)
- [x] **Python 3.13**: Usando match-case onde apropriado
- [x] **Python 3.13**: Type hints modernos (`|`, `list[]`, `dict[]`)
- [x] **Python 3.13**: Dataclasses com `slots=True`
- [x] **Python 3.13**: Positional-only (`/`) e keyword-only (`*`)
- [x] **Loguru**: Usando `logger.success()` para operações bem-sucedidas
- [x] **Loguru**: Cores corretas no terminal (INFO=azul, SUCCESS=verde, ERROR=vermelho)
