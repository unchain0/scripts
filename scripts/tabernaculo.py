"""Script para calcular o valor dos materiais do Tabernáculo em preços atuais."""

from dataclasses import dataclass

import pandas as pd
import yfinance as yf


@dataclass
class Material:
    """Representa um material com seus dados de peso e quantidade."""

    name: str
    ticker: str
    unit_weight: float
    talents: int
    shekels: int


# Dados dos materiais
MATERIALS_DATA = [
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

# Conversões de unidades
TALENT_TO_KG = 34.2  # 1 talent ≈ 34.2 kg
SHEKEL_TO_KG = 0.0114  # 1 shekel ≈ 11.4 g


def main() -> None:
    """Entry point for the script."""
    pd.options.display.float_format = "{:,.2f}".format

    # Cria DataFrame a partir dos dados dos materiais
    materials_df = pd.DataFrame([vars(m) for m in MATERIALS_DATA])
    materials_df.set_index("name", inplace=True)

    # Calcula o peso total em kg para cada material
    materials_df["weight_kg"] = (
        materials_df["talents"] * TALENT_TO_KG + materials_df["shekels"] * SHEKEL_TO_KG
    )

    # Obtém todos os tickers incluindo a taxa de câmbio BRL
    tickers_list = materials_df["ticker"].tolist() + ["BRL=X"]

    # Download de todos os preços em uma única requisição
    prices_df = yf.download(
        tickers=tickers_list, period="1d", progress=False, auto_adjust=True
    )["Close"].iloc[0]

    # Extrai a taxa USD/BRL
    usd_brl_rate = prices_df["BRL=X"]

    # Calcula o preço por kg em USD para cada material
    materials_df["price_usd_per_kg"] = materials_df.apply(
        lambda row: prices_df[row["ticker"]] / row["unit_weight"], axis=1
    )

    # Calcula o custo em USD e BRL para cada material
    materials_df["cost_usd"] = (
        materials_df["weight_kg"] * materials_df["price_usd_per_kg"]
    )
    materials_df["cost_brl"] = materials_df["cost_usd"] * usd_brl_rate

    # Exibe resultados
    print(materials_df[["weight_kg", "cost_usd", "cost_brl"]])
    print(f"\nTotal USD: ${materials_df['cost_usd'].sum():,.2f}")
    print(f"Total BRL: R${materials_df['cost_brl'].sum():,.2f}")


if __name__ == "__main__":
    main()
