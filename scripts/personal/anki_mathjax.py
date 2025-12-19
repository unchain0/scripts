r"""
O objetivo desse script é substituir em um arquivo chamado 'flashcards.csv'.
Os caracteres '$' por '\(' ou '\)' dependendo de onde '$' estiver na linha.

Por exemplo:

    - O texto '$(\vec{u} \times \vec{v}) \cdot \vec{w}$' ficaria assim
              '\(\vec{u} \times \vec{v}) \cdot \vec{w}\)'

Ou seja, se a linha a ser analisada contiver 2 '$' o primeiro será substituído por '\(\'
e o segundo por '\)', para cada abertura e fechamento ele deve seguir essa substituição.
"""

from pathlib import Path


def replace_dollar_signs(line: str) -> str:
    """
    Substitui os caracteres '$' por '\\(' e '\\)' alternadamente.
    O primeiro '$' vira '\\(', o segundo vira '\\)', e assim por diante.

    Args:
        line (str): Linha extraída do arquivo csv

    Returns:
        str: Texto com as substituições realizadas
    """
    result: list[str] = []
    is_opening = True

    for char in line:
        if char != "$":
            result.append(char)
            continue

        result.append(r"\(" if is_opening else r"\)")
        is_opening = not is_opening

    return "".join(result)


def valid_filepath(
    filepath: Path = Path(__file__).parent / "data" / "flashcards.csv",
) -> Path | None:
    """
    Valida o caminho do arquivo csv.

    Args:
        filepath (str): Caminho do arquivo

    Returns:
        bool: Verdadeiro se o caminho for válido, senão falso
    """
    if not filepath.exists():
        print(f"Error: File '{filepath}' not found.")
        return None
    return filepath


def main() -> None:
    if not (filepath := valid_filepath()):
        raise ValueError(f'Caminho do arquivo csv inválido "{filepath}"')

    content = filepath.read_text(encoding="utf-8")
    lines = content.splitlines(keepends=True)

    processed_lines = [replace_dollar_signs(line) for line in lines]
    new_content = "".join(processed_lines)

    new_filepath = filepath.parent / "flashcards_new.csv"
    new_filepath.write_text(new_content, encoding="utf-8")
    print(f"File '{new_filepath}' processed successfully.")


if __name__ == "__main__":
    main()
