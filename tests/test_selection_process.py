import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

# Add parent directory to path to import selection_process
sys.path.append(str(Path(__file__).parent.parent))
from selection_process import search_text_in_pdf


@dataclass
class TestCase:
    name: str
    file: str
    expected_page: int


@pytest.fixture
def downloads_dir() -> Path:
    return Path(__file__).parent.parent / "downloads"


def test_downloads_directory_exists(downloads_dir: Path) -> None:
    """Test if downloads directory exists"""
    assert downloads_dir.exists(), (
        "Downloads directory not found. Please run the main script first."
    )


TEST_CASES = [
    TestCase(
        name="SANDERSON SANTOS THEOPHILO CORREA",
        file="CHAMAMENTO PÚBLICO Nº 001_2025 – Convocação 007_2025 – PROGRAMA JOVEM CIDADÃO.pdf",
        expected_page=2,
    ),
    TestCase(
        name="VICTOR HUGO MELO DA SILVA",
        file="CHAMAMENTO PÚBLICO Nº 001_2025- Convocação 04_2025 – PROGRAMA JOVEM CIDADÃO.pdf",
        expected_page=2,
    ),
    TestCase(
        name="BRYAN ANGEL LEITE DOS SANTOS",
        file="CHAMAMENTO PÚBLICO Nº 001_2025- Convocação 01_2025 – PROGRAMA JOVEM CIDADÃO.pdf",
        expected_page=4,
    ),
]


@pytest.mark.parametrize("test_case", TEST_CASES)
def test_name_search_in_pdf(test_case: TestCase, downloads_dir: Path) -> None:
    """Test that each name is found in the correct file and page"""
    name = test_case.name
    file = test_case.file
    expected_page = test_case.expected_page

    # Build the full path to the PDF file
    filepath = downloads_dir / file

    # Check if file exists
    assert filepath.exists(), f"File {file} not found for testing {name}"

    # Search for the name in the PDF
    pages_found = search_text_in_pdf(filepath, name)

    # Check if the name was found in the expected page
    assert expected_page in pages_found, (
        f"Name '{name}' not found on page {expected_page} in file {file}. "
        f"Found on pages: {pages_found}"
    )

    print(f"PASS: Found '{name}' on page {expected_page} in {file}")
