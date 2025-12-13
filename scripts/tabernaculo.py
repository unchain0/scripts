from dataclasses import dataclass

import pandas as pd
import yfinance as yf

pd.options.display.float_format = "{:,.2f}".format


@dataclass
class Material:
    name: str
    ticker: str
    unit_weight: float
    talents: int
    shekels: int


# Material data
materials_data = [
    Material(
        name="Gold",
        ticker="GC=F",
        unit_weight=0.031103477,  # Troy ounce to kg
        talents=29,
        shekels=730,
    ),
    Material(
        name="Silver",
        ticker="SI=F",
        unit_weight=0.031103477,  # Troy ounce to kg
        talents=100,
        shekels=1775,
    ),
    Material(
        name="Copper",
        ticker="HG=F",
        unit_weight=0.45359237,  # Pound to kg
        talents=70,
        shekels=2400,
    ),
]

# Unit conversions
TALENT_TO_KG = 34.2  # 1 talent ≈ 34.2 kg
SHEKEL_TO_KG = 0.0114  # 1 shekel ≈ 11.4 g

# Create DataFrame from material data
materials_df = pd.DataFrame([vars(m) for m in materials_data])
materials_df.set_index("name", inplace=True)

# Calculate the total weight in kg for each material
materials_df["weight_kg"] = (
    materials_df["talents"] * TALENT_TO_KG + materials_df["shekels"] * SHEKEL_TO_KG
)

# Get all tickers including BRL exchange rate
tickers_list = materials_df["ticker"].tolist() + ["BRL=X"]

# Download all prices in a single request
prices_df = yf.download(
    tickers=tickers_list, period="1d", progress=False, auto_adjust=True
)["Close"].iloc[0]

# Extract USD/BRL rate
usd_brl_rate = prices_df["BRL=X"]

# Calculate the price per kg in USD for each material
materials_df["price_usd_per_kg"] = materials_df.apply(
    lambda row: prices_df[row["ticker"]] / row["unit_weight"], axis=1
)

# Calculate the cost in USD and BRL for each material
materials_df["cost_usd"] = materials_df["weight_kg"] * materials_df["price_usd_per_kg"]
materials_df["cost_brl"] = materials_df["cost_usd"] * usd_brl_rate

# Display results
print(materials_df[["weight_kg", "cost_usd", "cost_brl"]])
print(f"\nTotal USD: ${materials_df['cost_usd'].sum():,.2f}")
print(f"Total BRL: R${materials_df['cost_brl'].sum():,.2f}")
