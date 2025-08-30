"""
Script para automatizar a busca de nomes em documentos do Programa Jovem Cidadão de Saquarema.

Este script realiza as seguintes operações em sequência:
1. Acessa o site do chamamento público de Saquarema
2. Baixa automaticamente todos os PDFs relacionados ao Programa Jovem Cidadão do ano 2025
3. Permite buscar um nome ou texto específico em todos os PDFs baixados
4. Informa em quais arquivos e páginas o texto foi encontrado

Os PDFs são salvos na pasta 'downloads' e o script filtra apenas documentos que contenham
'PROGRAMA JOVEM CIDADÃO' e '2025' no título.
"""

from dataclasses import dataclass
from os import getenv
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag
from dotenv import load_dotenv
from pypdf import PdfReader
from tqdm import tqdm


@dataclass
class PdfLink:
    """Representa um link para um PDF do Programa Jovem Cidadão."""

    url: str
    title: str


@dataclass
class SearchResult:
    """Representa o resultado da busca em um arquivo PDF."""

    filename: str
    pages: list[int]


load_dotenv()


def get_pdf_links(url: str) -> list[PdfLink]:
    """
    Busca links de PDFs relacionados ao Programa Jovem Cidadão no site especificado.

    Args:
        url: URL do site de chamamento público

    Returns:
        Lista de PdfLink contendo URLs e títulos dos PDFs encontrados
    """
    response = requests.get(url)
    soup = BeautifulSoup(response.content, "html.parser")
    links = []
    all_links = soup.find_all("a")

    for link in all_links:
        if not isinstance(link, Tag):
            continue
        href = link.get("href")
        if (
            isinstance(href, str)
            and href.endswith(".pdf")
            and link.text.strip().startswith("CHAMAMENTO")
            and "PROGRAMA JOVEM CIDADÃO" in link.text
            and "2025" in link.text
        ):
            links.append(PdfLink(url=urljoin(url, href), title=link.text.strip()))

    return links


def download_pdf(url: str, filename: Path) -> Path | None:
    """
    Baixa um arquivo PDF da URL especificada.

    Args:
        url: URL do arquivo PDF
        filename: Nome do arquivo para salvar o PDF

    Returns:
        Caminho do arquivo salvo ou None se o download falhar
    """
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        downloads_path = Path("downloads")
        downloads_path.mkdir(exist_ok=True)
        filepath = downloads_path / filename
        with filepath.open("wb") as f:
            for data in response.iter_content(chunk_size=1024):
                f.write(data)
        return filepath
    return None


def send_notification(message: str) -> None:
    """
    Envia uma notificação usando ntfy.sh.

    Args:
        message: Mensagem a ser enviada
    """
    try:
        requests.post(
            "https://ntfy.sh/saquarema_jovem_cidadao",
            data=message.encode(encoding="utf-8"),
            headers={
                "Title": "PJC",
                "Priority": "urgent",
                "Tags": "rotating_light",
            },
        )
    except Exception as e:
        print(f"Failed to send notification: {e}")


def search_text_in_pdf(filepath: Path, search_text: str) -> list[int]:
    """
    Procura um texto específico em um arquivo PDF.

    Args:
        filepath: Caminho do arquivo PDF
        search_text: Texto a ser procurado

    Returns:
        Lista de números das páginas onde o texto foi encontrado
    """
    pages_found = []
    try:
        with filepath.open("rb") as file:
            reader = PdfReader(file)
            for page_num in range(len(reader.pages)):
                text = reader.pages[page_num].extract_text().lower()
                if search_text.lower() in text:
                    pages_found.append(page_num + 1)
        return pages_found
    except Exception as e:
        print(f"Failed to read file {filepath}: {e}")
        return []


def search_all_pdfs(search_text: str) -> list[SearchResult]:
    """
    Procura um texto em todos os PDFs da pasta 'downloads'.

    Args:
        search_text: Texto a ser procurado em todos os PDFs

    Returns:
        Lista de SearchResult contendo nome dos arquivos e páginas onde o texto foi encontrado
    """
    results: list[SearchResult] = []
    downloads_path = Path("downloads")
    if not downloads_path.exists():
        print("Directory 'downloads' not found. Please download PDFs first.")
        return results

    pdf_files = list(downloads_path.glob("*.pdf"))
    if not pdf_files:
        print("No PDF files found in 'downloads' directory.")
        return results

    with tqdm(pdf_files, desc="Procurando PDFs", unit="arquivo") as pbar:
        for filepath in pbar:
            pages = search_text_in_pdf(filepath, search_text)
            if pages:
                results.append(SearchResult(filename=filepath.name, pages=pages))

    return results


def main():
    """
    Função principal que executa o fluxo completo do programa:

    1. Baixa os PDFs encontrados
    2. Procura o nome no arquivo .env em todos os PDFs
    3. Envia notificação via ntfy.sh
    4. Exibe os resultados encontrados
    """

    # Get name from environment variable
    my_name = getenv("MY_NAME")
    if not my_name:
        print("Error: Environment variable MY_NAME not found")
        return

    # Step 1: Download PDFs
    url = "https://www.saquarema.rj.gov.br/chamamento-publico/"
    print("\nBaixando arquivos PDF...")
    pdf_links = get_pdf_links(url)

    success_count = 0
    failed_count = 0
    failed_files = []

    with tqdm(
        pdf_links,
        desc="Baixando PDFs",
        unit="arquivo",
        ncols=80,
        bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt}",
    ) as pbar:
        for link in pbar:
            filename = f"{link.title}.pdf".replace("/", "_")
            filepath = download_pdf(link.url, filename)
            if filepath:
                success_count += 1
            else:
                failed_count += 1
                failed_files.append(link.title)

    print(f"\n[+] {success_count} arquivos baixados com sucesso")
    if failed_files:
        print(f"[-] Falha ao baixar {failed_count} arquivos:")
        for file in failed_files:
            print(f"  - {file}")

    # Step 2: Search in PDFs
    print("\nProcurando nos PDFs...")
    results = search_all_pdfs(my_name)

    # Step 3: Show results and send notification if found
    if results:
        print("\nNome encontrado nos seguintes arquivos:")
        notification_message = "Seu nome foi encontrado nos seguintes arquivos:\n\n"
        for result in results:
            file_info = (
                f"{result.filename} (Páginas: {', '.join(map(str, result.pages))})"
            )
            print(f"\n[+] {file_info}")
            notification_message += f"📄 {file_info}\n"

        send_notification(notification_message)
    else:
        print(f"\nO nome '{my_name}' não foi encontrado em nenhum arquivo PDF.")


if __name__ == "__main__":
    main()
