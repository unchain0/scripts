"""Script para avaliar automaticamente artigos da base de conhecimento LiderBPO.

Author: Felippe Menezes - GHEF

Build executável standalone:
    cd scripts/work && ./build.sh

O executável inclui o Chromium embutido, não precisa de instalação adicional.
"""

import os
import queue
import sys
import threading
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText
from typing import Callable

if "PLAYWRIGHT_BROWSERS_PATH" in os.environ:
    del os.environ["PLAYWRIGHT_BROWSERS_PATH"]

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from loguru import logger
from PIL import Image, ImageTk
import keyring

BASE_URL = "https://liderbpo.app.br"
KB_URL = "https://liderbpo.app.br/politicas-e-procedimentos/base-conhecimento"
LOGIN_URL = "https://liderbpo.app.br/login"
STORAGE_FILE = Path(".suit_storage.json")
KEYRING_SERVICE = "liderbpo-rating"


class CredentialsManager:
    @staticmethod
    def save(email: str, password: str) -> None:
        keyring.set_password(KEYRING_SERVICE, "email", email)
        keyring.set_password(KEYRING_SERVICE, email, password)

    @staticmethod
    def load() -> tuple[str, str] | None:
        email = keyring.get_password(KEYRING_SERVICE, "email")
        if not email:
            return None
        password = keyring.get_password(KEYRING_SERVICE, email)
        if not password:
            return None
        return email, password

    @staticmethod
    def clear() -> None:
        email = keyring.get_password(KEYRING_SERVICE, "email")
        if email:
            keyring.delete_password(KEYRING_SERVICE, email)
            keyring.delete_password(KEYRING_SERVICE, "email")


class ConfigError(Exception):
    """Erro de configuração do sistema."""

    exit_code = 4


class NetworkError(Exception):
    """Erro de rede ou conectividade."""

    exit_code = 3


def load_credentials() -> tuple[str, str]:
    """Carrega as credenciais do arquivo .env.

    Returns:
        tuple[str, str]: Tupla contendo (email, senha).

    Raises:
        ConfigError: Se o arquivo .env não existir ou variáveis estiverem ausentes.
    """
    env_path = Path(".env")
    if not env_path.exists():
        raise ConfigError("Configuration file .env not found")

    load_dotenv(env_path)

    email = os.getenv("SUIT_EMAIL")
    password = os.getenv("SUIT_SENHA")

    if not email or not password:
        raise ConfigError("Missing SUIT_EMAIL or SUIT_SENHA in .env file")

    return email, password


# Cores do branding LiderBPO
COLORS: dict[str, str] = {
    "primary_blue": "#0F62AC",
    "accent_blue": "#2563EB",
    "bg_light": "#FAFAFA",
    "text_dark": "#111827",
    "white": "#FFFFFF",
    "gray_light": "#F3F4F6",
    "gray_border": "#E5E7EB",
    "yellow_accent": "#FDC82F",
}

# Cores para níveis Loguru no terminal
LOG_COLORS: dict[str, str] = {
    "TRACE": "#6B7280",
    "DEBUG": "#9CA3AF",
    "INFO": "#3B82F6",
    "SUCCESS": "#10B981",
    "WARNING": "#F59E0B",
    "ERROR": "#EF4444",
    "CRITICAL": "#DC2626",
}


class AuthError(Exception):
    """Erro de autenticação."""

    exit_code = 1


@dataclass(slots=True)
class LogRecord:
    """Record de log para a queue."""

    time: str
    level: str
    message: str


@dataclass(slots=True)
class ProgressUpdate:
    current: int
    total: int
    rated: int
    skipped: int
    last_title: str


@dataclass(slots=True)
class RatingResult:
    """Resultado do processo de avaliação."""

    rated: int
    skipped: int
    total: int
    success: bool = True
    error: str | None = None


class LoguruSink:
    def __init__(self, log_queue: queue.Queue[LogRecord], /):
        self._queue = log_queue

    def __call__(self, message) -> None:
        record = message.record
        msg = record["message"]
        if ":" in msg:
            msg = msg.split(":")[0]
        self._queue.put(
            LogRecord(
                time=record["time"].strftime("%H:%M:%S"),
                level=record["level"].name,
                message=msg,
            )
        )


class LogTerminal(ttk.Frame):
    """Terminal de log em tempo real com Loguru."""

    def __init__(self, parent, /):
        super().__init__(parent)
        self._queue: queue.Queue[LogRecord] = queue.Queue()
        self._text = ScrolledText(
            self,
            state="disabled",
            font=("Consolas", 10),
            bg="#1F2937",
            fg="#F9FAFB",
            wrap="word",
        )
        self._text.pack(fill="both", expand=True)
        self._setup_tags()
        self._handler_id: int | None = None

    def _setup_tags(self) -> None:
        for level, color in LOG_COLORS.items():
            self._text.tag_configure(level, foreground=color)

    def start_logging(self) -> None:
        """Inicia o logging para este terminal."""
        logger.remove()
        self._handler_id = logger.add(
            LoguruSink(self._queue),
            format="{message}",
            colorize=False,
            diagnose=False,
        )
        self._poll()

    def _poll(self) -> None:
        while True:
            try:
                if record := self._queue.get_nowait():
                    self._display(record)
            except queue.Empty:
                break
        self.after(100, self._poll)

    def _display(self, record: LogRecord, /) -> None:
        self._text.configure(state="normal")
        line = f"[{record.time}] [{record.level:8}] {record.message}\n"
        self._text.insert("end", line, record.level)
        self._text.configure(state="disabled")
        self._text.see("end")


def get_asset_path(filename: str) -> Path:
    """Retorna o caminho para um asset, funcionando em modo frozen e script."""
    if getattr(sys, "frozen", False):
        base_path = Path(sys._MEIPASS)
    else:
        base_path = Path(__file__).parent
    return base_path / "assets" / filename


class LoginFrame(ttk.Frame):
    def __init__(self, parent, on_login, /):
        super().__init__(parent)
        self._on_login = on_login
        self._setup_ui()
        self._load_saved_credentials()

    def _load_saved_credentials(self) -> None:
        if creds := CredentialsManager.load():
            self._email_var.set(creds[0])
            self._password_var.set(creds[1])

    def _setup_ui(self) -> None:
        # Container principal
        container = ttk.Frame(self, padding=20)
        container.pack(expand=True)

        # Email
        ttk.Label(container, text="E-mail:", font=("TkDefaultFont", 11)).pack(
            anchor="w", pady=(0, 5)
        )
        self._email_var = tk.StringVar()
        self._email_entry = ttk.Entry(
            container,
            textvariable=self._email_var,
            width=40,
            font=("TkDefaultFont", 11),
        )
        self._email_entry.pack(pady=(0, 15))

        # Senha
        ttk.Label(container, text="Senha:", font=("TkDefaultFont", 11)).pack(
            anchor="w", pady=(0, 5)
        )
        self._password_var = tk.StringVar()
        self._password_entry = ttk.Entry(
            container,
            textvariable=self._password_var,
            width=40,
            font=("TkDefaultFont", 11),
            show="•",
        )
        self._password_entry.pack(pady=(0, 20))

        # Botão
        self._login_btn = tk.Button(
            container,
            text="Entrar",
            font=("TkDefaultFont", 12, "bold"),
            bg=COLORS["accent_blue"],
            fg=COLORS["white"],
            activebackground=COLORS["primary_blue"],
            activeforeground=COLORS["white"],
            cursor="hand2",
            relief="flat",
            padx=30,
            pady=10,
            command=self._handle_login,
        )
        self._login_btn.pack()

        # Bind Enter key
        self._password_entry.bind("<Return>", lambda e: self._handle_login())

    def _handle_login(self) -> None:
        email = self._email_var.get().strip()
        password = self._password_var.get()
        if email and password:
            self._on_login(email, password)

    def get_credentials(self) -> tuple[str, str]:
        """Retorna as credenciais inseridas."""
        return self._email_var.get().strip(), self._password_var.get()


class AuthManager:
    """Gerencia autenticação e sessão do Playwright."""

    def __init__(self, email: str, password: str, storage_path: Path, /):
        self._email = email
        self._password = password
        self._storage_path = storage_path

    @property
    def email(self) -> str:
        return self._email

    def has_valid_session(self) -> bool:
        """Verifica se existe uma sessão salva."""
        return self._storage_path.exists()

    def login(self, page) -> None:
        """Realiza login no site."""
        page.goto(LOGIN_URL)
        page.get_by_role("textbox", name="E-mail").fill(self._email)
        page.get_by_role("textbox", name="Senha").fill(self._password)
        page.get_by_role("button", name="Entrar no sistema").click()

        # Aguarda navegação
        page.wait_for_load_state("networkidle")

        # Verifica se login foi bem sucedido
        if "login" in page.url.lower():
            raise AuthError("Login failed - invalid credentials")

    def save_session(self, context) -> None:
        """Salva o estado da sessão."""
        context.storage_state(path=str(self._storage_path))

    def load_session(self, browser):
        """Carrega contexto com sessão salva."""
        return browser.new_context(storage_state=str(self._storage_path))


class LiderBPOApp(tk.Tk):
    """Aplicação principal com GUI Tkinter."""

    def __init__(self):
        super().__init__()
        self.title("LiderBPO - Avaliador de Base de Conhecimento")
        self.geometry("850x650")
        self.configure(bg=COLORS["bg_light"])
        self._setup_ui()

    def _setup_ui(self) -> None:
        header = tk.Frame(self, bg=COLORS["primary_blue"], height=80)
        header.pack(fill="x")
        header.pack_propagate(False)

        try:
            logo_path = get_asset_path("logo_white.png")
            if logo_path.exists():
                img = Image.open(logo_path)
                img = img.resize((150, 47), Image.Resampling.LANCZOS)
                self._logo_image = ImageTk.PhotoImage(img)
                logo_label = tk.Label(
                    header, image=self._logo_image, bg=COLORS["primary_blue"]
                )
                logo_label.pack(pady=15)
        except Exception:
            tk.Label(
                header,
                text="LiderBPO",
                font=("TkDefaultFont", 20, "bold"),
                bg=COLORS["primary_blue"],
                fg=COLORS["white"],
            ).pack(pady=20)

        self._main_container = ttk.Frame(self)
        self._main_container.pack(fill="both", expand=True)

        self._dash_frame = ttk.Frame(self._main_container, padding=20)

        stats_container = ttk.Frame(self._dash_frame)
        stats_container.pack(fill="x", pady=(0, 20))

        self._total_var = tk.StringVar(value="0")
        self._rated_var = tk.StringVar(value="0")
        self._skipped_var = tk.StringVar(value="0")

        self._create_stat_card(stats_container, "Total", self._total_var, 0)
        self._create_stat_card(stats_container, "Avaliados", self._rated_var, 1)
        self._create_stat_card(stats_container, "Pulados", self._skipped_var, 2)

        ttk.Label(
            self._dash_frame, text="Progresso Geral:", font=("TkDefaultFont", 10)
        ).pack(anchor="w")
        self._progress_var = tk.DoubleVar()
        self._progress_bar = ttk.Progressbar(
            self._dash_frame,
            variable=self._progress_var,
            maximum=100,
            length=400,
            mode="determinate",
        )
        self._progress_bar.pack(fill="x", pady=(5, 20))

        self._log_terminal = LogTerminal(self._dash_frame)
        self._log_terminal.pack(fill="both", expand=True)

        self._login_frame = LoginFrame(self._main_container, self._on_login)
        self._login_frame.pack(fill="both", expand=True)

        footer = tk.Frame(self, bg=COLORS["bg_light"])
        footer.pack(fill="x", side="bottom")
        tk.Label(
            footer,
            text="Felippe Menezes - GHEF",
            font=("TkDefaultFont", 8),
            bg=COLORS["bg_light"],
            fg="#9CA3AF",
        ).pack(pady=5)

    def _create_stat_card(self, parent, label, variable, column):
        card = tk.Frame(
            parent, bg=COLORS["white"], bd=1, relief="solid", padx=15, pady=10
        )
        card.grid(row=0, column=column, padx=5, sticky="nsew")
        parent.columnconfigure(column, weight=1)

        tk.Label(
            card,
            text=label,
            font=("TkDefaultFont", 10),
            bg=COLORS["white"],
            fg=COLORS["text_dark"],
        ).pack()
        tk.Label(
            card,
            textvariable=variable,
            font=("TkDefaultFont", 16, "bold"),
            bg=COLORS["white"],
            fg=COLORS["primary_blue"],
        ).pack()

    def _on_login(self, email: str, password: str) -> None:
        self._login_frame.pack_forget()
        self._dash_frame.pack(fill="both", expand=True)
        self._log_terminal.start_logging()

        CredentialsManager.save(email, password)
        logger.info(f"Starting with user")

        worker = RatingWorker(
            email,
            password,
            on_complete=self._on_worker_complete,
            on_progress=self._on_progress,
        )
        worker.start()

    def _on_progress(self, update: ProgressUpdate) -> None:
        """Atualiza a interface com o progresso do worker."""
        self._total_var.set(str(update.total))
        self._rated_var.set(str(update.rated))
        self._skipped_var.set(str(update.skipped))

        if update.total > 0:
            percent = (update.current / update.total) * 100
            self._progress_var.set(percent)

        self.update_idletasks()

    def _on_worker_complete(self, result: RatingResult) -> None:
        """Callback quando worker termina."""
        if result.success:
            logger.success(
                f"Summary: {result.rated} rated, {result.skipped} skipped, {result.total} total"
            )
        else:
            logger.error(f"Process failed: {result.error}")

    def show_login(self) -> None:
        """Mostra o frame de login."""
        self._log_terminal.pack_forget()
        self._login_frame.pack(fill="both", expand=True)

    def show_terminal(self) -> None:
        """Mostra o terminal de log."""
        self._login_frame.pack_forget()
        self._log_terminal.pack(fill="both", expand=True, padx=10, pady=10)
        self._log_terminal.start_logging()


class SelectorError(Exception):
    """Erro de seletor não encontrado."""

    exit_code = 2


@dataclass(slots=True)
class ArticleInfo:
    """Informações de um artigo da base de conhecimento."""

    url: str
    title: str


class KnowledgeBaseScraper:
    """Scraper para coletar e avaliar artigos."""

    def __init__(self, page, /):
        self._page = page

    def collect_all_article_urls(self, max_pages: int = 50) -> list[ArticleInfo]:
        articles: list[ArticleInfo] = []
        current_page = 0
        previous_first_url: str | None = None

        logger.info("Collecting article URLs...")

        while current_page < max_pages:
            current_page += 1
            logger.debug(f"Processing page {current_page}...")

            self._wait_for_table_update(previous_first_url)

            page_articles = self._page.evaluate("""
                () => {
                    const results = [];
                    const rows = document.querySelectorAll('table tbody tr');
                    rows.forEach(row => {
                        const cells = row.querySelectorAll('td');
                        if (cells.length > 0) {
                            const titleCell = cells[0];
                            const title = titleCell ? titleCell.textContent.trim() : 'Unknown';
                            const link = row.querySelector('a[href*="/artigo/"]');
                            if (link) {
                                results.push({ url: link.href, title });
                            }
                        }
                    });
                    return results;
                }
            """)

            if page_articles:
                previous_first_url = page_articles[0]["url"]

            for item in page_articles:
                articles.append(ArticleInfo(url=item["url"], title=item["title"]))

            logger.debug(f"Page {current_page}: found {len(page_articles)} articles")

            next_btn = self._page.locator(
                'button:has-text("›"):not(:has-text("»")):not([disabled])'
            )
            if next_btn.count() == 0:
                logger.debug("No enabled next button found")
                break

            next_btn.first.click()

        logger.info(f"Collected {len(articles)} articles from {current_page} pages")
        return articles

    def _wait_for_table_update(self, previous_first_url: str | None) -> None:
        try:
            loading = self._page.locator('text="Carregando..."')
            loading.wait_for(state="visible", timeout=2000)
            loading.wait_for(state="hidden", timeout=30000)
        except Exception:
            pass

        self._page.locator('table tbody tr a[href*="/artigo/"]').first.wait_for(
            state="visible", timeout=10000
        )

        if previous_first_url:
            for _ in range(50):
                current_first = self._page.evaluate("""
                    () => {
                        const link = document.querySelector('table tbody tr a[href*="/artigo/"]');
                        return link ? link.href : null;
                    }
                """)
                if current_first and current_first != previous_first_url:
                    break
                self._page.wait_for_timeout(100)

    def is_already_rated(self) -> bool:
        """Verifica se o artigo já foi avaliado."""
        return (
            self._page.get_by_role(
                "heading", name="Você já avaliou este artigo"
            ).count()
            > 0
        )

    def get_article_title(self) -> str:
        """Retorna o título do artigo atual."""
        heading = self._page.get_by_role("heading", level=1).first
        text = heading.text_content()
        if text and text.startswith("Artigo:"):
            return text[7:].strip()
        return text.strip() if text else "Unknown"

    def rate_article(self) -> None:
        """Avalia o artigo com 5 estrelas."""
        # Encontra o container de avaliação
        rating_label = self._page.get_by_text("Avaliação *")
        if rating_label.count() == 0:
            raise SelectorError("Rating container not found")

        # Encontra os botões de estrelas
        rating_container = rating_label.locator("..").locator("..")
        stars = rating_container.get_by_role("button").all()

        if len(stars) < 5:
            raise SelectorError(f"Expected 5 star buttons, found {len(stars)}")

        # Clica na 5ª estrela
        stars[4].click()

        # Clica em Enviar Avaliação
        submit_btn = self._page.get_by_role("button", name="Enviar Avaliação")
        submit_btn.wait_for(state="visible", timeout=5000)

        if not submit_btn.is_enabled():
            raise SelectorError("Submit button is disabled")

        submit_btn.click()

        # Confirma no modal
        self._page.get_by_role("button", name="Confirmar").click()

        # Aguarda redirecionamento
        self._page.wait_for_load_state("networkidle")


class RatingWorker(threading.Thread):
    def __init__(
        self,
        email: str,
        password: str,
        /,
        *,
        on_complete: Callable[[RatingResult], None],
        on_progress: Callable[[ProgressUpdate], None] | None = None,
    ):
        super().__init__(daemon=True)
        self._email = email
        self._password = password
        self._on_complete = on_complete
        self._on_progress = on_progress

    def run(self) -> None:
        result = self._execute()
        self._on_complete(result)

    def _execute(self) -> RatingResult:
        rated = 0
        skipped = 0
        total = 0

        try:
            logger.info("Iniciando navegador...")

            with sync_playwright() as p:
                browser = None
                # Ordem de preferência para navegadores instalados no sistema
                channels = ["msedge", "chrome", "chromium"]

                for channel in channels:
                    try:
                        logger.debug(f"Tentando canal: {channel}")
                        browser = p.chromium.launch(headless=True, channel=channel)
                        logger.info(f"Navegador iniciado usando: {channel}")
                        break
                    except Exception:
                        continue

                if not browser:
                    try:
                        logger.debug("Tentando canal: firefox")
                        browser = p.firefox.launch(headless=True)
                        logger.info("Navegador iniciado usando: firefox")
                    except Exception:
                        pass

                if not browser:
                    try:
                        logger.warning(
                            "Canais específicos falharam. Tentando lançamento padrão..."
                        )
                        browser = p.chromium.launch(headless=True)
                    except Exception:
                        raise NetworkError(
                            "Nenhum navegador compatível encontrado (Edge/Chrome/Chromium)."
                        )

                auth = AuthManager(self._email, self._password, STORAGE_FILE)

                context = None
                page = None

                if auth.has_valid_session():
                    logger.info("Loading saved session...")
                    context = auth.load_session(browser)
                    page = context.new_page()
                    page.goto(KB_URL, wait_until="networkidle")
                    logger.debug(f"Current URL after session load: {page.url}")

                    if "login" in page.url.lower():
                        logger.warning("Session expired, forcing new login...")
                        context.close()
                        context = None
                        page = None
                        STORAGE_FILE.unlink(missing_ok=True)

                if context is None:
                    logger.info(f"Logging in as {self._email}...")
                    context = browser.new_context()
                    page = context.new_page()
                    auth.login(page)
                    auth.save_session(context)
                    logger.success("Session saved")

                assert page is not None

                if page.url != KB_URL:
                    logger.info("Navigating to knowledge base...")
                    page.goto(KB_URL, wait_until="networkidle")
                else:
                    logger.debug("Already on knowledge base page, skipping navigation")

                scraper = KnowledgeBaseScraper(page)

                if articles := scraper.collect_all_article_urls():
                    logger.info(f"Found {len(articles)} articles")
                    total = len(articles)
                else:
                    logger.warning("No articles found")
                    return RatingResult(0, 0, 0)

                for i, article in enumerate(articles, 1):
                    page.goto(article.url)
                    title = article.title

                    match scraper.is_already_rated():
                        case True:
                            logger.info(
                                f'[{i}/{total}] "{title}" - ALREADY RATED, skipping'
                            )
                            skipped += 1
                        case False:
                            logger.info(f'[{i}/{total}] "{title}" - RATING...')
                            scraper.rate_article()
                            logger.success(f'[{i}/{total}] "{title}" - RATED ✓')
                            rated += 1

                    if self._on_progress:
                        self._on_progress(
                            ProgressUpdate(
                                current=i,
                                total=total,
                                rated=rated,
                                skipped=skipped,
                                last_title=title,
                            )
                        )

                browser.close()

            logger.success(
                f"Completed: Rated {rated}, Skipped {skipped}, Total {total}"
            )
            return RatingResult(rated, skipped, total)

        except AuthError as e:
            logger.error(f"Authentication failed: {e}")
            e.add_note(f"Email: {self._email}")
            return RatingResult(rated, skipped, total, success=False, error=str(e))

        except SelectorError as e:
            logger.error(f"Selector not found: {e}")
            return RatingResult(rated, skipped, total, success=False, error=str(e))

        except Exception as e:
            logger.exception("Unexpected error")
            return RatingResult(rated, skipped, total, success=False, error=str(e))


if __name__ == "__main__":
    app = LiderBPOApp()
    app.mainloop()
