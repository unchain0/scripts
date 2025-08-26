#!/usr/bin/env -S uv run --script

from pathlib import Path

import yfinance as yf

data_dir = Path().parent.absolute() / "data"
data_dir.mkdir(exist_ok=True)
btc_csv = data_dir / "bitcoin.csv"

try:
    btc = yf.Ticker("BTC-USD")
    df_btc = btc.history(period="max")
    df_btc.to_csv(btc_csv)
except Exception:
    print("Failed to download BTC data.")
