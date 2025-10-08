"""
Script que pressiona as teclas Z, X e C automaticamente a cada 10 segundos.
"""

import time

import keyboard
from enum import Enum


class Key(Enum):
    Z = "z"
    X = "x"
    C = "c"


def press_keys(keys: list[Key]) -> None:
    """Pressiona as teclas Z, X e C em sequência."""
    for key in keys:
        keyboard.press_and_release(key.value)
        print(f"Pressed: {key.value}")
        time.sleep(0.1)


def main(*, seconds: int, keys: list[Key]) -> None:
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
    main(
        seconds=10,
        keys=[Key.Z, Key.X, Key.C],
    )
