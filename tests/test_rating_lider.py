"""Testes unitários para o script de avaliação da base de conhecimento LiderBPO."""

import queue
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.append(str(Path(__file__).parents[1]))

from scripts.work.rating_lider import (
    BASE_URL,
    KB_URL,
    LOGIN_URL,
    STORAGE_FILE,
    AuthError,
    AuthManager,
    ConfigError,
    load_credentials,
    LogRecord,
    LoguruSink,
    NetworkError,
    RatingResult,
    RatingWorker,
)


def test_constants_defined():
    """Verifica que as constantes estão definidas com valores corretos."""
    assert BASE_URL == "https://liderbpo.app.br"
    assert (
        KB_URL == "https://liderbpo.app.br/politicas-e-procedimentos/base-conhecimento"
    )
    assert LOGIN_URL == "https://liderbpo.app.br/login"
    assert STORAGE_FILE == Path(".suit_storage.json")


def test_load_credentials_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Verifica carregamento bem-sucedido de credenciais."""
    env_file = tmp_path / ".env"
    env_file.write_text("SUIT_EMAIL=test@example.com\nSUIT_SENHA=secret123\n")
    monkeypatch.chdir(tmp_path)

    email, password = load_credentials()

    assert email == "test@example.com"
    assert password == "secret123"


def test_load_credentials_missing_env_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Verifica erro quando arquivo .env não existe."""
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ConfigError) as exc_info:
        load_credentials()

    assert "not found" in str(exc_info.value).lower()
    assert exc_info.value.exit_code == 4


def test_load_credentials_missing_vars(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Verifica erro quando variáveis obrigatórias estão ausentes."""
    env_file = tmp_path / ".env"
    env_file.write_text("SUIT_EMAIL=test@example.com\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("SUIT_SENHA", raising=False)

    with pytest.raises(ConfigError) as exc_info:
        load_credentials()

    assert "missing" in str(exc_info.value).lower()
    assert exc_info.value.exit_code == 4


class TestLoguruSink:
    """Testes para LoguruSink."""

    def test_loguru_sink_puts_record_in_queue(self):
        """Verifica que LoguruSink coloca records na queue."""
        log_queue: queue.Queue[LogRecord] = queue.Queue()
        sink = LoguruSink(log_queue)

        mock_message = MagicMock()
        mock_level = MagicMock()
        mock_level.name = "INFO"
        mock_message.record = {
            "time": MagicMock(strftime=lambda fmt: "10:30:15"),
            "level": mock_level,
            "message": "Test message",
        }

        sink(mock_message)

        assert not log_queue.empty()
        record = log_queue.get()
        assert record.time == "10:30:15"
        assert record.level == "INFO"
        assert record.message == "Test message"


class TestAuthManager:
    """Testes para AuthManager."""

    def test_auth_manager_login_success(self):
        """Verifica login bem-sucedido."""
        auth = AuthManager("test@example.com", "secret", Path("/tmp/storage.json"))

        mock_page = MagicMock()
        mock_page.url = "https://liderbpo.app.br/dashboard"

        auth.login(mock_page)

        mock_page.get_by_role.assert_any_call("textbox", name="E-mail")
        mock_page.get_by_role.assert_any_call("textbox", name="Senha")
        mock_page.get_by_role.assert_any_call("button", name="Entrar no sistema")

    def test_auth_manager_saves_cookies(self, tmp_path: Path):
        """Verifica que sessão é salva."""
        storage_path = tmp_path / "storage.json"
        auth = AuthManager("test@example.com", "secret", storage_path)

        mock_context = MagicMock()
        auth.save_session(mock_context)

        mock_context.storage_state.assert_called_once_with(path=str(storage_path))

    def test_auth_manager_uses_saved_cookies(self, tmp_path: Path):
        """Verifica que sessão existente é detectada."""
        storage_path = tmp_path / "storage.json"
        storage_path.write_text("{}")

        auth = AuthManager("test@example.com", "secret", storage_path)

        assert auth.has_valid_session() is True

    def test_auth_manager_login_failure(self):
        """Verifica que login falho levanta AuthError."""
        auth = AuthManager("test@example.com", "wrong", Path("/tmp/storage.json"))

        mock_page = MagicMock()
        mock_page.url = "https://liderbpo.app.br/login"

        with pytest.raises(AuthError) as exc_info:
            auth.login(mock_page)

        assert exc_info.value.exit_code == 1


from scripts.work.rating_lider import (
    ArticleInfo,
    KnowledgeBaseScraper,
    SelectorError,
)


class TestKnowledgeBaseScraper:
    def test_scraper_collect_articles_single_page_with_table(self):
        mock_page = MagicMock()

        mock_loading = MagicMock()
        mock_loading.wait_for = MagicMock()
        mock_page.locator.return_value = mock_loading

        mock_page.evaluate.return_value = [
            {"url": "https://example.com/artigo/1", "title": "Article 1"},
            {"url": "https://example.com/artigo/2", "title": "Article 2"},
        ]

        mock_next_btn = MagicMock()
        mock_next_btn.count.return_value = 0

        def locator_side_effect(selector):
            if "›" in selector:
                return mock_next_btn
            return mock_loading

        mock_page.locator.side_effect = locator_side_effect

        scraper = KnowledgeBaseScraper(mock_page)
        articles = scraper.collect_all_article_urls()

        assert len(articles) == 2
        assert articles[0].title == "Article 1"
        assert articles[1].url == "https://example.com/artigo/2"

    def test_scraper_collect_articles_with_pagination(self):
        mock_page = MagicMock()

        mock_loading = MagicMock()
        mock_loading.wait_for = MagicMock()
        mock_row = MagicMock()
        mock_row.wait_for = MagicMock()
        mock_loading.first = mock_row

        evaluate_results = [
            [{"url": "https://example.com/artigo/1", "title": "Page 1 Article"}],
            "https://example.com/artigo/2",
            [{"url": "https://example.com/artigo/2", "title": "Page 2 Article"}],
            None,
        ]
        mock_page.evaluate.side_effect = evaluate_results
        mock_page.wait_for_timeout = MagicMock()

        next_btn_count = [0]

        def locator_side_effect(selector):
            if "›" in selector:
                next_btn_count[0] += 1
                mock_next = MagicMock()
                mock_next.count.return_value = 1 if next_btn_count[0] < 2 else 0
                mock_next.first = MagicMock()
                return mock_next
            if "Carregando" in selector:
                return mock_loading
            if "table tbody tr" in selector:
                return mock_row
            return mock_loading

        mock_page.locator.side_effect = locator_side_effect

        scraper = KnowledgeBaseScraper(mock_page)
        articles = scraper.collect_all_article_urls()

        assert len(articles) == 2
        assert articles[0].title == "Page 1 Article"
        assert articles[1].title == "Page 2 Article"

    def test_scraper_waits_for_loading_to_disappear(self):
        mock_page = MagicMock()

        mock_loading = MagicMock()
        mock_loading.wait_for = MagicMock()
        mock_row = MagicMock()
        mock_row.wait_for = MagicMock()
        mock_loading.first = mock_row

        mock_next = MagicMock()
        mock_next.count.return_value = 0

        def locator_side_effect(selector):
            if "›" in selector:
                return mock_next
            if "Carregando" in selector:
                return mock_loading
            if "table tbody tr" in selector:
                return mock_row
            return mock_loading

        mock_page.locator.side_effect = locator_side_effect
        mock_page.evaluate.return_value = []

        scraper = KnowledgeBaseScraper(mock_page)
        scraper.collect_all_article_urls()

        mock_loading.wait_for.assert_any_call(state="visible", timeout=2000)
        mock_loading.wait_for.assert_any_call(state="hidden", timeout=30000)

    def test_scraper_respects_max_pages_limit(self):
        mock_page = MagicMock()

        mock_loading = MagicMock()
        mock_loading.wait_for = MagicMock()
        mock_row = MagicMock()
        mock_row.wait_for = MagicMock()
        mock_loading.first = mock_row

        def evaluate_side_effect(js_code):
            if "querySelectorAll" in js_code:
                return [{"url": "https://example.com/artigo/1", "title": "Article"}]
            return "https://example.com/artigo/2"

        mock_page.evaluate.side_effect = evaluate_side_effect
        mock_page.wait_for_timeout = MagicMock()

        mock_next = MagicMock()
        mock_next.count.return_value = 1
        mock_next.first = MagicMock()

        def locator_side_effect(selector):
            if "›" in selector:
                return mock_next
            if "Carregando" in selector:
                return mock_loading
            if "table tbody tr" in selector:
                return mock_row
            return mock_loading

        mock_page.locator.side_effect = locator_side_effect

        scraper = KnowledgeBaseScraper(mock_page)
        articles = scraper.collect_all_article_urls(max_pages=3)

        assert len(articles) == 3

    def test_scraper_handles_empty_table(self):
        mock_page = MagicMock()

        mock_loading = MagicMock()
        mock_loading.wait_for = MagicMock()
        mock_row = MagicMock()
        mock_row.wait_for = MagicMock()
        mock_loading.first = mock_row

        mock_page.evaluate.return_value = []

        mock_next = MagicMock()
        mock_next.count.return_value = 0

        def locator_side_effect(selector):
            if "›" in selector:
                return mock_next
            if "Carregando" in selector:
                return mock_loading
            if "table tbody tr" in selector:
                return mock_row
            return mock_loading

        mock_page.locator.side_effect = locator_side_effect

        scraper = KnowledgeBaseScraper(mock_page)
        articles = scraper.collect_all_article_urls()

        assert articles == []

    def test_scraper_is_already_rated_true(self):
        """Verifica detecção de artigo já avaliado."""
        mock_page = MagicMock()
        mock_page.get_by_role.return_value.count.return_value = 1

        scraper = KnowledgeBaseScraper(mock_page)
        result = scraper.is_already_rated()

        assert result is True
        mock_page.get_by_role.assert_called_with(
            "heading", name="Você já avaliou este artigo"
        )

    def test_scraper_is_already_rated_false(self):
        """Verifica detecção de artigo não avaliado."""
        mock_page = MagicMock()
        mock_page.get_by_role.return_value.count.return_value = 0

        scraper = KnowledgeBaseScraper(mock_page)
        result = scraper.is_already_rated()

        assert result is False

    def test_scraper_rate_article_success(self):
        """Verifica avaliação bem-sucedida."""
        mock_page = MagicMock()

        # Mock rating container
        mock_label = MagicMock()
        mock_label.count.return_value = 1
        mock_page.get_by_text.return_value = mock_label

        # Mock stars
        mock_stars = [MagicMock() for _ in range(5)]
        mock_container = MagicMock()
        mock_container.get_by_role.return_value.all.return_value = mock_stars
        mock_label.locator.return_value.locator.return_value = mock_container

        # Mock submit button
        mock_submit = MagicMock()
        mock_submit.is_enabled.return_value = True
        mock_page.get_by_role.return_value = mock_submit

        scraper = KnowledgeBaseScraper(mock_page)
        scraper.rate_article()

        # Verify 5th star was clicked
        mock_stars[4].click.assert_called_once()

    def test_scraper_rate_article_submit_disabled(self):
        """Verifica erro quando botão submit está desabilitado."""
        mock_page = MagicMock()

        # Mock rating container
        mock_label = MagicMock()
        mock_label.count.return_value = 1
        mock_page.get_by_text.return_value = mock_label

        # Mock stars
        mock_stars = [MagicMock() for _ in range(5)]
        mock_container = MagicMock()
        mock_container.get_by_role.return_value.all.return_value = mock_stars
        mock_label.locator.return_value.locator.return_value = mock_container

        # Mock submit button DISABLED
        mock_submit = MagicMock()
        mock_submit.is_enabled.return_value = False
        mock_page.get_by_role.return_value = mock_submit

        scraper = KnowledgeBaseScraper(mock_page)

        with pytest.raises(SelectorError):
            scraper.rate_article()


class TestNetworkError:
    """Testes para NetworkError."""

    def test_network_error_exit_code(self):
        """Verifica que NetworkError tem exit_code correto."""
        assert NetworkError.exit_code == 3


class TestRatingResult:
    """Testes para RatingResult."""

    def test_rating_result_slots(self):
        """Verifica que RatingResult usa slots."""
        assert hasattr(RatingResult, "__slots__")

    def test_rating_result_default_values(self):
        """Verifica valores padrão do RatingResult."""
        result = RatingResult(rated=5, skipped=3, total=8)
        assert result.success is True
        assert result.error is None

    def test_rating_result_with_error(self):
        """Verifica RatingResult com erro."""
        result = RatingResult(
            rated=0, skipped=0, total=0, success=False, error="Test error"
        )
        assert result.success is False
        assert result.error == "Test error"


class TestRatingWorker:
    """Testes para RatingWorker."""

    def test_worker_thread_runs_in_background(self):
        """Verifica que worker é daemon thread."""
        callback = MagicMock()
        worker = RatingWorker("test@example.com", "password", on_complete=callback)
        assert worker.daemon is True

    def test_worker_logs_via_loguru(self, monkeypatch: pytest.MonkeyPatch):
        """Verifica que worker usa loguru para logs."""
        from loguru import logger as loguru_logger

        log_messages = []
        monkeypatch.setattr(
            loguru_logger, "info", lambda msg: log_messages.append(("info", msg))
        )
        monkeypatch.setattr(
            loguru_logger, "error", lambda msg: log_messages.append(("error", msg))
        )
        monkeypatch.setattr(
            loguru_logger,
            "exception",
            lambda msg: log_messages.append(("exception", msg)),
        )

        # Mock sync_playwright para evitar inicialização real
        mock_playwright = MagicMock()
        mock_playwright.__enter__ = MagicMock(
            side_effect=Exception("Test browser error")
        )
        mock_playwright.__exit__ = MagicMock(return_value=False)

        from scripts.work import rating_lider

        monkeypatch.setattr(rating_lider, "sync_playwright", lambda: mock_playwright)

        callback = MagicMock()
        worker = RatingWorker("test@example.com", "password", on_complete=callback)
        worker._execute()

        # Deve ter logado "Iniciando navegador..."
        assert any("Iniciando navegador" in msg for _, msg in log_messages)

    def test_worker_handles_errors(self, monkeypatch: pytest.MonkeyPatch):
        """Verifica que worker trata erros e retorna RatingResult com success=False."""
        from loguru import logger as loguru_logger

        monkeypatch.setattr(loguru_logger, "info", MagicMock())
        monkeypatch.setattr(loguru_logger, "error", MagicMock())
        monkeypatch.setattr(loguru_logger, "exception", MagicMock())

        # Mock sync_playwright para lançar erro
        mock_playwright = MagicMock()
        mock_playwright.__enter__ = MagicMock(side_effect=Exception("Browser crash"))
        mock_playwright.__exit__ = MagicMock(return_value=False)

        from scripts.work import rating_lider

        monkeypatch.setattr(rating_lider, "sync_playwright", lambda: mock_playwright)

        callback = MagicMock()
        worker = RatingWorker("test@example.com", "password", on_complete=callback)
        result = worker._execute()

        assert result.success is False
        assert result.error is not None
        assert "Browser crash" in result.error

    def test_app_shows_summary_on_completion(self, monkeypatch: pytest.MonkeyPatch):
        """Verifica que app mostra summary quando worker completa."""
        from loguru import logger as loguru_logger

        log_messages = []
        monkeypatch.setattr(
            loguru_logger, "success", lambda msg: log_messages.append(("success", msg))
        )
        monkeypatch.setattr(
            loguru_logger, "error", lambda msg: log_messages.append(("error", msg))
        )

        from scripts.work.rating_lider import LiderBPOApp

        # Mock Tk para evitar inicialização da GUI
        mock_tk = MagicMock()
        monkeypatch.setattr("tkinter.Tk.__init__", lambda self: None)
        monkeypatch.setattr("tkinter.Tk.title", lambda self, t: None)
        monkeypatch.setattr("tkinter.Tk.geometry", lambda self, g: None)
        monkeypatch.setattr("tkinter.Tk.configure", lambda self, **kw: None)

        # Testa o callback diretamente
        from scripts.work.rating_lider import RatingResult

        app = object.__new__(LiderBPOApp)
        result = RatingResult(rated=10, skipped=5, total=15, success=True)
        app._on_worker_complete(result)

        assert any("10 rated" in msg and "5 skipped" in msg for _, msg in log_messages)
