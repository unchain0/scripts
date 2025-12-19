"""
Script para instalar automaticamente extensões do Visual Studio Code.

Este script usa uma classe para gerenciar extensões do VS Code,
permitindo instalar, remover e listar extensões.
"""

import subprocess
import sys
from dataclasses import dataclass, field

from loguru import logger

# Lista de IDs das extensões do VS Code para instalar
# https://hl2guide.github.io/Awesome-Visual-Studio-Code-Extensions/
EXTENSIONS = [
    # Recommended Extensions
    "RoscoP.ActiveFileInStatusBar",  # Active File In StatusBar
    "formulahendry.auto-close-tag",  # Auto Close Tag
    "formulahendry.auto-rename-tag",  # Auto Rename Tag
    "aaron-bond.better-comments",  # Better Comments
    "1nVitr0.blocksort",  # Block Sort
    "alefragnani.Bookmarks",  # Bookmarks
    "chunsen.bracket-select",  # Bracket Select
    "naumovs.color-highlight",  # Color Highlight
    "stackbreak.comment-divider",  # Comment Divider
    "jianbingfang.dupchecker",  # DupChecker
    "geeebe.duplicate",  # Duplicate selection or line
    "usernamehw.errorlens",  # Error Lens
    "mkxml.vscode-filesize",  # Filesize
    "miguelsolorio.fluent-icons",  # Fluent Icons
    "eliostruyf.vscode-hide-comments",  # Hide Comments
    "wengerk.highlight-bad-chars",  # Highlight Bad Chars
    "cliffordfajardo.highlight-line-vscode",  # Highlight Line
    "vincaslt.highlight-matching-tag",  # Highlight Matching Tag
    "mguellsegarra.highlight-on-copy",  # Highlight on Copy
    "jasonlhy.hungry-delete",  # Hungry Delete
    "eklemen.hungry-backspace",  # Hungry-Backspace
    "sandipchitale.vscode-indent-line",  # Indent line
    "oderwat.indent-rainbow",  # Indent-rainbow
    "jsynowiec.vscode-insertdatestring",  # Insert Date String
    "emilast.LogFileHighlighter",  # Log File Highlighter
    "bierner.markdown-checkbox",  # Markdown Checkboxes
    "IBM.output-colorizer",  # Output Colorizer
    "Rubymaniac.vscode-paste-and-indent",  # Paste and Indent
    "christian-kohler.path-intellisense",  # Path Intellisense
    "earshinov.permute-lines",  # Permute Lines
    "alefragnani.read-only-indicator",  # Read-Only Indicator
    "usernamehw.remove-empty-lines",  # Remove Empty Lines
    "redlin.remove-tabs-on-save",  # Remove Tabs On Save
    "medo64.render-crlf",  # Render Line Endings
    "karizma.scoped-sort",  # Scoped Sort
    "StAlYo.select-quotes",  # Select-quotes
    "mrvautin.selecta",  # Selecta
    "gurumukhi.selected-lines-count",  # Selected Lines Count
    "cyansprite.smoothscroll",  # Smoothscroll
    "earshinov.sort-lines-by-selection",  # Sort Lines by Selection
    "Tyriar.sort-lines",  # Sort lines
    "ryu1kn.text-marker",  # Text Marker (Highlighter)
    "qcz.text-power-tools",  # Text Power Tools
    "datasert.vscode-texty",  # Texty
    "davidhouchin.whitespace-plus",  # Whitespace+
    "sketchbuch.vsc-workspace-sidebar",  # Workspace Sidebar
    "stneveadomi.grepc",  # grepc: Regex Highlighting
    "PedroAlves1122.vscode-minify",  # vscode-minify
    # Specialized Extensions
    "PedroAlves1122.vscode-minify",  # Auto-Minify
    "mark-wiemer.vscode-autohotkey-plus-plus",  # AutoHotkey Plus Plus
    "formulahendry.code-runner",  # Code Runner
    "nmsmith89.incrementor",  # Incrementor
    "mdickin.markdown-shortcuts",  # Markdown Shortcuts
    "ms-vscode.powershell",  # PowerShell
    "ms-python.python",  # Python
    "mechatroner.rainbow-csv",  # Rainbow CSV
    "slevesque.shader",  # Shader languages support
    "koalamer.workspace-in-status-bar",  # Workspace Name in Status Bar
    "bmuskalla.vscode-tldr",  # tl;dr pages
]


@dataclass
class VSCodeExtensionManager:
    """Gerenciador de extensões do Visual Studio Code."""

    extensions_to_install: list[str] = field(default_factory=lambda: EXTENSIONS.copy())
    _success_count: int = field(default=0, init=False)
    _fail_count: int = field(default=0, init=False)
    _failed_extensions: list[str] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        """Verifica se o VS Code está instalado após inicialização."""
        self._check_vscode_installed()

    def _check_vscode_installed(self) -> None:
        """Verifica se o VS Code está instalado e acessível via linha de comando."""
        try:
            result = subprocess.run(
                ["code", "--version"], capture_output=True, text=True, check=False
            )
            if result.returncode != 0:
                raise FileNotFoundError
        except FileNotFoundError:
            logger.error("VS Code não encontrado!")
            logger.error(
                "Certifique-se de que o VS Code está instalado e o comando 'code' "
                "está disponível no PATH do sistema."
            )
            sys.exit(1)

    def _run_code_command(self, *args: str) -> subprocess.CompletedProcess[str]:
        """Executa um comando do VS Code.

        Args:
            *args: Argumentos para o comando 'code'.

        Returns:
            subprocess.CompletedProcess: Resultado da execução do comando.
        """
        return subprocess.run(
            ["code", *args],
            capture_output=True,
            text=True,
            check=False,
        )

    def _reset_counters(self) -> None:
        """Reseta os contadores de sucesso e falha."""
        self._success_count = 0
        self._fail_count = 0
        self._failed_extensions.clear()

    def list_installed(self) -> list[str | None]:
        """Obtém a lista de extensões instaladas no VS Code.

        Returns:
            list[str]: Lista de IDs das extensões instaladas.
        """
        try:
            result = self._run_code_command("--list-extensions")
            if result.returncode == 0:
                return [
                    ext.strip()
                    for ext in result.stdout.strip().split("\n")
                    if ext.strip()
                ]
        except Exception as e:
            logger.exception(f"Erro ao listar extensões: {e}")
        return []

    def install(self, extension_id: str) -> bool:
        """Instala uma extensão do VS Code.

        Args:
            extension_id: O identificador da extensão no marketplace.

        Returns:
            bool: True se a instalação foi bem-sucedida, False caso contrário.
        """
        logger.info(f"Instalando: {extension_id}...")

        try:
            result = self._run_code_command(
                "--install-extension", extension_id, "--force"
            )

            if result.returncode == 0:
                logger.success(f"{extension_id} instalada com sucesso!")
                return True

            logger.error(f"Erro ao instalar {extension_id}")
            if err := result.stderr:
                logger.debug(f"Detalhes: {err.strip()}")

        except Exception as e:
            logger.exception(f"Exceção ao instalar {extension_id}: {e}")

        return False

    def uninstall(self, extension_id: str) -> bool:
        """Remove uma extensão do VS Code.

        Args:
            extension_id (str): O identificador da extensão no marketplace.

        Returns:
            bool: True se a remoção foi bem-sucedida, False caso contrário.
        """
        logger.info(f"Removendo: {extension_id}...")

        try:
            result = self._run_code_command("--uninstall-extension", extension_id)

            if result.returncode == 0:
                logger.success(f"{extension_id} removida com sucesso!")
                return True

            logger.error(f"Erro ao remover {extension_id}")
            if err := result.stderr:
                logger.debug(f"Detalhes: {err.strip()}")

        except Exception as e:
            logger.exception(f"Exceção ao remover {extension_id}: {e}")

        return False

    def install_all(self) -> None:
        """Instala todas as extensões da lista."""
        self._reset_counters()
        total = len(self.extensions_to_install)

        logger.info(f"Total de extensões para instalar: {total}")

        for i, extension in enumerate(self.extensions_to_install, 1):
            logger.info(f"[{i}/{total}]")

            if self.install(extension):
                self._success_count += 1
            else:
                self._fail_count += 1
                self._failed_extensions.append(extension)

        self._log_summary("instaladas", "instalação")

    def uninstall_all(self) -> None:
        """Remove todas as extensões instaladas no VS Code."""
        self._reset_counters()
        extensions = self.list_installed()

        if not extensions:
            logger.info("Nenhuma extensão instalada para remover.")
            return

        total = len(extensions)
        logger.info(f"Total de extensões para remover: {total}")

        for i, extension in enumerate(extensions, 1):
            logger.info(f"[{i}/{total}]")

            if extension is None:
                logger.warning(f"Extensão não encontrada: {extension}")
                break

            if self.uninstall(extension):
                self._success_count += 1
            else:
                self._fail_count += 1
                self._failed_extensions.append(extension)

        self._log_summary("removidas", "remoção")

    def _log_summary(self, action_past: str, action_noun: str) -> None:
        """Exibe o resumo da operação.

        Args:
            action_past: Verbo no particípio (ex: 'instaladas', 'removidas').
            action_noun: Substantivo da ação (ex: 'instalação', 'remoção').
        """
        logger.success(f"Extensões {action_past} com sucesso: {self._success_count}")

        if self._fail_count > 0:
            logger.warning(f"Extensões com falha na {action_noun}: {self._fail_count}")

        if self._failed_extensions:
            logger.warning("Extensões que falharam:")
            for ext in self._failed_extensions:
                logger.warning(f"  - {ext}")
            logger.info("Você pode tentar manualmente usando:")
            logger.info("  code --install-extension <extension-id>")
            logger.info("  code --uninstall-extension <extension-id>")

    @property
    def has_failures(self) -> bool:
        """Verifica se houve falhas na última operação."""
        return self._fail_count > 0


def ask_yes_no(prompt: str) -> bool:
    """Pergunta ao usuário uma questão sim/não.

    Args:
        prompt: A pergunta a ser exibida.

    Returns:
        bool: True se o usuário confirmar, False caso contrário.
    """
    while True:
        response = input(prompt).strip().lower()

        if response in ("s", "sim", "y", "yes"):
            return True
        elif response in ("n", "nao", "não", "no"):
            return False
        else:
            logger.warning(
                "Resposta inválida. Por favor, digite 's' para sim ou 'n' para não."
            )


def main() -> None:
    """Função principal que gerencia as extensões do VS Code."""
    manager = VSCodeExtensionManager()

    if ask_yes_no(
        "Deseja deletar todas as extensões do VS Code antes de instalar? (s/n): "
    ):
        logger.info("Iniciando remoção de todas as extensões...")
        manager.uninstall_all()
        logger.info("Remoção concluída. Iniciando instalação das novas extensões...")

    manager.install_all()
    logger.info("Processo concluído!")

    sys.exit(0 if not manager.has_failures else 1)


if __name__ == "__main__":
    main()
