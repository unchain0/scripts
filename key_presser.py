"""Script que pressiona as teclas automaticamente a cada X segundos."""

import argparse
import time

import keyboard
from string import ascii_lowercase


def press_keys(keys: list[str]) -> None:
    """Pressiona as teclas fornecidas em sequência."""
    if not keys:
        raise ValueError("Keys list cannot be empty")

    for key in keys:
        if (key := key.lower()) not in ascii_lowercase:
            raise ValueError(f"Key {key} is not a lowercase letter")

        keyboard.press_and_release(key)
        print(f"Pressed: {key}")
        time.sleep(0.1)


def main(*, seconds: int, keys: list[str]) -> None:
    """Loop principal que pressiona as teclas a cada X segundos."""
    print("Starting key presser... Press Ctrl+C to stop")

    try:
        while True:
            press_keys(keys=keys)
            print(f"Waiting {seconds} seconds...")
            time.sleep(seconds)
    except KeyboardInterrupt:
        print("\nStopped by user")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Script que pressiona teclas automaticamente em intervalos regulares"
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

    args = parser.parse_args()

    main(
        seconds=args.seconds,
        keys=args.keys,
    )
