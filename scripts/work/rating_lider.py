"""Script para avaliar automaticamente artigos da base de conhecimento LiderBPO.

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

BASE_URL = "https://liderbpo.app.br"
KB_URL = "https://liderbpo.app.br/politicas-e-procedimentos/base-conhecimento"
LOGIN_URL = "https://liderbpo.app.br/login"
STORAGE_FILE = Path(".suit_storage.json")


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
    """Sink thread-safe que envia logs para queue."""

    def __init__(self, log_queue: queue.Queue[LogRecord], /):
        self._queue = log_queue

    def __call__(self, message) -> None:
        record = message.record
        self._queue.put(
            LogRecord(
                time=record["time"].strftime("%H:%M:%S"),
                level=record["level"].name,
                message=record["message"],
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
    """Frame de login com logo e campos de credenciais."""

    def __init__(self, parent, on_login, /):
        super().__init__(parent)
        self._on_login = on_login
        self._setup_ui()

    def _setup_ui(self) -> None:
        # Container principal
        container = ttk.Frame(self, padding=20)
        container.pack(expand=True)

        # Email
        ttk.Label(container, text="E-mail:", font=("Segoe UI", 11)).pack(
            anchor="w", pady=(0, 5)
        )
        self._email_var = tk.StringVar()
        self._email_entry = ttk.Entry(
            container, textvariable=self._email_var, width=40, font=("Segoe UI", 11)
        )
        self._email_entry.pack(pady=(0, 15))

        # Senha
        ttk.Label(container, text="Senha:", font=("Segoe UI", 11)).pack(
            anchor="w", pady=(0, 5)
        )
        self._password_var = tk.StringVar()
        self._password_entry = ttk.Entry(
            container,
            textvariable=self._password_var,
            width=40,
            font=("Segoe UI", 11),
            show="•",
        )
        self._password_entry.pack(pady=(0, 20))

        # Botão
        self._login_btn = tk.Button(
            container,
            text="Entrar",
            font=("Segoe UI", 12, "bold"),
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
        self.geometry("700x650")
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
                font=("Segoe UI", 20, "bold"),
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
            self._dash_frame, text="Progresso Geral:", font=("Segoe UI", 10)
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

    def _create_stat_card(self, parent, label, variable, column):
        card = tk.Frame(
            parent, bg=COLORS["white"], bd=1, relief="solid", padx=15, pady=10
        )
        card.grid(row=0, column=column, padx=5, sticky="nsew")
        parent.columnconfigure(column, weight=1)

        tk.Label(
            card,
            text=label,
            font=("Segoe UI", 10),
            bg=COLORS["white"],
            fg=COLORS["text_dark"],
        ).pack()
        tk.Label(
            card,
            textvariable=variable,
            font=("Segoe UI", 16, "bold"),
            bg=COLORS["white"],
            fg=COLORS["primary_blue"],
        ).pack()

    def _on_login(self, email: str, password: str) -> None:
        """Callback quando usuário faz login."""
        self._login_frame.pack_forget()
        self._dash_frame.pack(fill="both", expand=True)
        self._log_terminal.start_logging()

        logger.info(f"Starting with user: {email}")

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

    def collect_all_article_urls(self) -> list[ArticleInfo]:
        """Coleta todos os URLs de artigos de todas as páginas."""
        articles: list[ArticleInfo] = []

        while True:
            # Aguarda carregamento
            loading = self._page.get_by_text("Carregando...")
            if loading.count() > 0:
                loading.first.wait_for(state="hidden", timeout=10000)

            # Coleta artigos da página atual
            links = self._page.get_by_role("link", name="Visualizar").all()
            for link in links:
                href = link.get_attribute("href")
                if href:
                    # URL completa
                    url = href if href.startswith("http") else f"{BASE_URL}{href}"
                    # Tenta extrair título do card pai
                    try:
                        card = link.locator(
                            "xpath=ancestor::div[contains(@class, 'card')]"
                        )
                        title_elem = card.locator("h3, h4, .card-title").first
                        title = title_elem.text_content() or "Unknown"
                    except Exception:
                        title = "Unknown"
                    articles.append(ArticleInfo(url=url, title=title.strip()))

            # Verifica se há próxima página
            next_btn = self._page.get_by_role("button", name="»")
            if next_btn.count() == 0 or not next_btn.is_enabled():
                break
            next_btn.click()
            self._page.wait_for_load_state("networkidle")

        return articles

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
            logger.info("Starting browser (Edge)...")

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, channel="msedge")
                auth = AuthManager(self._email, self._password, STORAGE_FILE)

                if auth.has_valid_session():
                    logger.info("Loading saved session...")
                    context = auth.load_session(browser)
                else:
                    logger.info(f"Logging in as {self._email}...")
                    context = browser.new_context()
                    page = context.new_page()
                    auth.login(page)
                    auth.save_session(context)
                    logger.success("Session saved ✓")

                page = context.new_page()
                page.goto(KB_URL)

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
