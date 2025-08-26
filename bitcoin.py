#!/usr/bin/env -S uv run --script
# /// script
# dependencies = ["yfinance"]
# ///

import yfinance as yf  # type: ignore[import-untyped]


def get_bitcoin_price() -> float:
    """
    Fetches the current Bitcoin price in USD using yfinance.

    Returns:
        float: The current Bitcoin price in USD, rounded to 2 decimal places.
    """
    btc = yf.Ticker("BTC-USD")
    price = btc.history(period="1d")["Close"].iloc[0]
    return round(price, 2)


print(f" {get_bitcoin_price():,.2f}")
