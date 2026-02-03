import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).parents[1]))

from scripts.selection_process import search_text_in_pdf


@dataclass
class CaseData:
    name: str
    file: str
    expected_page: int


TEST_CASES: list[CaseData] = [
    CaseData(
        name="VICTOR HUGO MELO DA SILVA",
        file="CHAMAMENTO PÚBLICO Nº 001_2025- Convocação 04_2025 – PROGRAMA JOVEM CIDADÃO.pdf",
        expected_page=2,
    ),
    CaseData(
        name="BRYAN ANGEL LEITE DOS SANTOS",
        file="CHAMAMENTO PÚBLICO Nº 001_2025- Convocação 01_2025 – PROGRAMA JOVEM CIDADÃO.pdf",
        expected_page=4,
    ),
]


@pytest.fixture
def downloads_dir() -> Path:
    """Path to the downloads' directory.

    Returns:
        Path: Path to the downloads' directory.
    """
    return Path(__file__).parent.parent / "downloads"


def test_downloads_directory_exists(downloads_dir: Path) -> None:
    """Test if downloads directory exists.

    Args:
        downloads_dir (Path): Path to the downloads' directory.
    """
    downloads_dir.mkdir(exist_ok=True)
    assert downloads_dir.exists(), "Downloads directory not found."


@pytest.mark.parametrize("test_case", TEST_CASES)
def test_name_search_in_pdf(test_case: CaseData, downloads_dir: Path) -> None:
    """Test that each name is found in the correct file and page.

    Args:
        test_case (CaseData): Test case data.
        downloads_dir (Path): Path to the downloads' directory.
    """
    name = test_case.name
    file = test_case.file
    expected_page = test_case.expected_page
    filepath = downloads_dir / file

    if not filepath.exists():
        pytest.skip(f"Test PDF file not found: {file}")

    pages_found = search_text_in_pdf(filepath, name)

    assert expected_page in pages_found, (
        f"Name '{name}' not found on page {expected_page} in file {file}. "
        f"Found on pages: {pages_found}"
    )
