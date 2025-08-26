import webbrowser
from string import Template
from time import perf_counter
from typing import Iterable
from urllib.parse import quote

words: list[str] = input("Enter the words to search (comma separated): ").split(",")

TPL = Template(
    "https://dicionario.reverso.net/ingles-definicao/${word}#translation=portuguese"
)


def normalize(token: str) -> str:
    return token.strip().lower()


def build_url(word: str) -> str:
    encoded = quote(word, safe="")
    return TPL.substitute(word=encoded)


def open_words(items: Iterable[str]) -> None:
    seen: set[str] = set()
    first = True
    for token in items:
        norm = normalize(token)
        if not norm or norm in seen:
            continue
        seen.add(norm)
        url = build_url(norm)
        if first:
            webbrowser.open_new_tab(url)
            first = False
        else:
            webbrowser.open(url)


start = perf_counter()
open_words(words)
elapsed = perf_counter() - start
print(f"Tempo total: {elapsed:.3f}s")
