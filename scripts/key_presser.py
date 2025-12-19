"""Script que pressiona as teclas automaticamente a cada X segundos."""

import argparse
import time
from string import ascii_lowercase

import keyboard


def press_keys(keys: list[str], press_interval: int = 1) -> None:
    """Pressiona as teclas fornecidas em sequência.

    Args:
        keys (list[str]): Lista de teclas para pressionar
        press_interval (int, optional): Time a segundo para pressionar. Defaults to 1.
    """
    if not keys:
        raise ValueError("Keys list cannot be empty")

    for key in keys:
        if (key := key.lower()) not in ascii_lowercase:
            raise ValueError(f"Key {key} is not a lowercase letter")

        keyboard.press_and_release(key)
        print(f"Pressed: {key}")
        time.sleep(press_interval)


def main(*, wait: int, keys: list[str]) -> None:
    """Loop principal que pressiona as teclas a cada X segundos.

    Args:
        wait (int): Tempo de espera em segundos até outra execução
        keys (list[str]): Lista de teclas para pressionar
    """
    print("Starting key presser... Press Ctrl+C to stop")

    try:
        while True:
            press_keys(keys=keys)
            print(f"Waiting {wait} seconds...")
            time.sleep(wait)
    except KeyboardInterrupt:
        print("\nStopped by user")


def parse_args() -> argparse.Namespace:
    """Parse os argumentos de entrada."""
    parser = argparse.ArgumentParser(
        prog="key_presser",
        description="Script que pressiona teclas automaticamente em intervalos regulares",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-s",
        "--seconds",
        type=int,
        default=5,
        help="Intervalo em segundos entre cada execução (padrão: 5)",
    )
    parser.add_argument(
        "-k",
        "--keys",
        nargs="+",
        default=["Z", "X", "C"],
        help="Teclas a serem pressionadas (padrão: Z X C)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    main(
        wait=args.seconds,
        keys=args.keys,
    )
