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

import os
from urllib.parse import urljoin

import PyPDF2
import requests
from bs4 import BeautifulSoup, Tag
from tqdm import tqdm


def get_pdf_links(url: str) -> list[dict[str, str]]:
    """
    Busca links de PDFs relacionados ao Programa Jovem Cidadão no site especificado.

    Args:
        url: URL do site de chamamento público.

    Returns:
        Lista de dicionários contendo URLs e títulos dos PDFs encontrados.
        Cada dicionário tem as chaves 'url' e 'title'.
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
            links.append({"url": urljoin(url, href), "title": link.text.strip()})

    return links


def download_pdf(url: str, filename: str) -> str | None:
    """
    Baixa um arquivo PDF da URL especificada.

    Args:
        url: URL do arquivo PDF.
        filename: Nome do arquivo para salvar o PDF.

    Returns:
        Caminho do arquivo salvo ou None se o download falhar.
    """
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        os.makedirs("downloads", exist_ok=True)
        filepath = os.path.join("downloads", filename)
        with open(filepath, "wb") as f:
            for data in response.iter_content(chunk_size=1024):
                f.write(data)
        return filepath
    return None


def search_text_in_pdf(filepath: str, search_text: str) -> list[int]:
    """
    Procura um texto específico em um arquivo PDF.

    Args:
        filepath: Caminho do arquivo PDF.
        search_text: Texto a ser procurado.

    Returns:
        Lista de números das páginas onde o texto foi encontrado.
    """
    pages_found = []
    try:
        with open(filepath, "rb") as file:
            reader = PyPDF2.PdfReader(file)
            for page_num in range(len(reader.pages)):
                text = reader.pages[page_num].extract_text().lower()
                if search_text.lower() in text:
                    pages_found.append(page_num + 1)
        return pages_found
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return []


def search_all_pdfs(search_text: str) -> dict[str, list[int]]:
    """
    Procura um texto em todos os PDFs da pasta 'downloads'.

    Args:
        search_text: Texto a ser procurado em todos os PDFs.

    Returns:
        Dicionário com nome dos arquivos como chaves e lista de páginas como valores.
    """
    results: dict[str, list[int]] = {}
    downloads_dir = "downloads"
    if not os.path.exists(downloads_dir):
        print("Downloads directory not found. Please download PDFs first.")
        return results

    pdf_files = [f for f in os.listdir(downloads_dir) if f.endswith(".pdf")]
    if not pdf_files:
        print("No PDF files found in downloads directory.")
        return results

    with tqdm(pdf_files, desc="Searching PDFs", unit="file") as pbar:
        for pdf_file in pbar:
            filepath = os.path.join(downloads_dir, pdf_file)
            pages = search_text_in_pdf(filepath, search_text)
            if pages:
                results[pdf_file] = pages

    return results


def main():
    """
    Função principal que executa o fluxo completo do programa:
    1. Baixa os PDFs do site
    2. Solicita o texto para busca
    3. Procura o texto em todos os PDFs
    4. Exibe os resultados encontrados
    """
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
            filename = f"{link['title']}.pdf".replace("/", "_")
            filepath = download_pdf(link["url"], filename)
            if filepath:
                success_count += 1
            else:
                failed_count += 1
                failed_files.append(link["title"])

    print(f"\n[+] {success_count} arquivos baixados com sucesso")
    if failed_files:
        print(f"[-] Falha ao baixar {failed_count} arquivos:")
        for file in failed_files:
            print(f"  - {file}")

    # Step 2: Search in PDFs
    search_text = input("\nDigite o texto que deseja procurar nos PDFs: ")
    print("\nProcurando nos PDFs...")
    results = search_all_pdfs(search_text)

    # Step 3: Show results and exit
    if results:
        print("\nTexto encontrado nos seguintes arquivos:")
        for pdf_file, pages in results.items():
            print(f"\n[+] {pdf_file}")
            print(f"    Encontrado na(s) página(s): {', '.join(map(str, pages))}")
    else:
        print(f"\nO texto '{search_text}' não foi encontrado em nenhum arquivo PDF.")


if __name__ == "__main__":
    main()
