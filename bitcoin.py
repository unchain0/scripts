import yfinance as yf


def get_bitcoin_price() -> float | None:
    """
    Fetches the current Bitcoin price in USD using yfinance.

    Returns:
        (float | None): The current Bitcoin price in USD, rounded to 2 decimal places.
    """
    btc = yf.Ticker("BTC-USD")
    price = btc.history(period="1d")["Close"].iloc[0]

    if isinstance(price, float):
        return round(price, 2)
    return None


print(f" {get_bitcoin_price():,.2f}")
