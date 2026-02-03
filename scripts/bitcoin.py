"""Script para obter o preço atual do Bitcoin em USD."""

from curl_cffi.requests.exceptions import CertificateVerifyError

import yfinance as yf


def get_bitcoin_price() -> float | None:
    """Fetch the current Bitcoin price in USD using yfinance.

    Returns:
        (float | None): The current Bitcoin price in USD, rounded to 2 decimal places.
    """
    btc = yf.Ticker("BTC-USD")

    try:
        price = btc.history(period="1d")["Close"].iloc[0]
    except CertificateVerifyError as e:
        print(e)
        return None

    if isinstance(price, float):
        return round(price, 2)
    return None


def main() -> None:
    """Entry point for the script."""
    if bitcoin_price := get_bitcoin_price():
        print(f" {bitcoin_price:,.2f}")


if __name__ == "__main__":
    main()
