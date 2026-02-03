import logging
import shutil
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

warnings.simplefilter(action="ignore", category=FutureWarning)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# =============================================================================
# PATHS
# =============================================================================
ROOT_DIR = Path(__file__).parents[1]
PASTA_EXTRATOS = ROOT_DIR / "data" / "extratos"
ARQUIVO_SAIDA = ROOT_DIR / "data" / "Bradesco_Master_Cronologico.csv"
ARQUIVO_DASHBOARD_DATA = ROOT_DIR / "data" / "Bradesco_Dashboard_Data.csv"
DASHBOARD_PATH = ROOT_DIR / "output" / "Dashboard_Financeiro"

# =============================================================================
# CONSTANTES - PROCESSAMENTO DE EXTRATOS
# =============================================================================
HEADER_ROW = 6
MIN_COLUNAS = 6
COLUNAS_ESPERADAS = ["Data", "Historico", "Documento", "Credito", "Debito", "Saldo"]
FORMATO_DATA = "%d/%m/%y"
MARCADORES_BRADESCO = ["Bradesco", "BRADESCO", "Banco Bradesco"]
PALAVRAS_IGNORAR = ["Saldo", "Extrato"]
SEPARADOR_CSV = ";"
DECIMAL_CSV = ","
MAX_WORKERS = 4

# =============================================================================
# CONSTANTES - DASHBOARD
# =============================================================================
CORES = {
    "primary": "#0078D4",
    "success": "#107C10",
    "danger": "#D13438",
    "warning": "#FFB900",
    "background": "#F3F2F1",
    "white": "#FFFFFF",
    "dark": "#323130",
}
CANVAS_WIDTH = 1280
CANVAS_HEIGHT = 720
CARD_HEIGHT = 100
CARD_WIDTH = 280
CHART_HEIGHT = 280
TABLE_HEIGHT = 260


# =============================================================================
# FUNÇÕES - PROCESSAMENTO DE EXTRATOS
# =============================================================================
def limpar_numero(val: Any) -> float:
    """
    Converte um valor para float, tratando formatos brasileiros.

    Args:
        val: Valor a ser convertido (pode ser string, número ou NaN).

    Returns:
        Valor numérico float ou 0.0 se inválido.
    """
    if pd.isna(val):
        return 0.0

    val_str = str(val).strip()
    if val_str in ["-", "", "nan"]:
        return 0.0

    try:
        return float(val_str.replace(".", "").replace(",", "."))
    except ValueError:
        logger.warning(f"Unable to convert value to float: {val_str}")
        return 0.0


def validar_arquivo_bradesco(df: pd.DataFrame, caminho: Path) -> bool:
    """
    Valida se o DataFrame corresponde a um extrato válido do Bradesco.

    Args:
        df: DataFrame carregado do arquivo.
        caminho: Caminho do arquivo para logging.

    Returns:
        True se válido, False caso contrário.
    """
    if len(df.columns) < MIN_COLUNAS:
        logger.warning(
            f"File {caminho.name} has insufficient columns: {len(df.columns)}"
        )
        return False

    nome_arquivo = caminho.name.upper()
    if not any(marcador.upper() in nome_arquivo for marcador in MARCADORES_BRADESCO):
        logger.warning(f"File {caminho.name} doesn't appear to be a Bradesco file")
        return False

    if df.empty:
        logger.warning(f"File {caminho.name} is empty")
        return False

    return True


def agrupar_linhas_quebradas(df: pd.DataFrame) -> list[pd.Series]:
    """
    Agrupa linhas quebradas de transações em uma única linha.

    Extratos do Bradesco frequentemente quebram o histórico em múltiplas linhas.
    Esta função identifica e concatena essas linhas.

    Args:
        df: DataFrame com possíveis linhas quebradas.

    Returns:
        Lista de Series, cada uma representando uma transação completa.
    """
    df["TransactionID"] = df["Data"].notna().cumsum()
    rows: list[pd.Series] = []

    for _, group in df.groupby("TransactionID"):
        if len(group) == 0:
            continue

        main_row = group.iloc[0].copy()

        if len(group) > 1:
            extras = group.iloc[1:]["Historico"].dropna().astype(str).tolist()
            if extras:
                extras_limpos = [
                    x
                    for x in extras
                    if not any(palavra in x for palavra in PALAVRAS_IGNORAR)
                ]
                if extras_limpos:
                    main_row["Historico"] = (
                        str(main_row["Historico"]) + " " + " ".join(extras_limpos)
                    )

        rows.append(main_row)

    return rows


def processar_arquivo_bradesco(caminho_arquivo: Path) -> pd.DataFrame | None:
    """
    Processa um único arquivo de extrato do Bradesco.

    Args:
        caminho_arquivo: Caminho para o arquivo XLS/XLSX.

    Returns:
        DataFrame processado ou None se inválido.
    """
    nome_arq = caminho_arquivo.name
    logger.debug(f"Processing file: {nome_arq}")

    df: pd.DataFrame | None = None

    try:
        df = pd.read_excel(caminho_arquivo, header=HEADER_ROW)
    except (ValueError, FileNotFoundError) as e:
        logger.debug(f"Failed to read {nome_arq} as Excel: {e}")
        try:
            df = pd.read_html(str(caminho_arquivo), header=HEADER_ROW)[0]
        except (ValueError, IndexError) as e:
            logger.error(f"Failed to read file {nome_arq}: {e}")
            return None

    if df is None:
        return None

    if not validar_arquivo_bradesco(df, caminho_arquivo):
        return None

    df = df.iloc[:, :MIN_COLUNAS]
    df.columns = COLUNAS_ESPERADAS

    df = df[df["Data"] != "Data"]
    df = df.dropna(subset=["Data", "Historico"], how="all")

    rows = agrupar_linhas_quebradas(df)

    df_clean = pd.DataFrame(rows)

    df_clean["Data"] = pd.to_datetime(
        df_clean["Data"], format=FORMATO_DATA, errors="coerce"
    )
    df_clean = df_clean.dropna(subset=["Data"])

    if df_clean.empty:
        logger.warning(f"No valid data in file {nome_arq}")
        return None

    for col in ["Credito", "Debito", "Saldo"]:
        df_clean[col] = df_clean[col].apply(limpar_numero)

    df_clean["Valor"] = df_clean["Credito"] + df_clean["Debito"]
    df_clean["Arquivo_Origem"] = nome_arq

    logger.debug(f"Successfully processed {nome_arq}: {len(df_clean)} transactions")
    return df_clean


def recalcular_saldo(df: pd.DataFrame) -> pd.DataFrame:
    """
    Recalcula o saldo cumulativo baseado nos valores das transações.

    Args:
        df: DataFrame ordenado cronologicamente.

    Returns:
        DataFrame com coluna Saldo recalculada.
    """
    saldo_inicial = 0.0
    primeira_linha_com_saldo = df[df["Saldo"] != 0].head(1)

    if not primeira_linha_com_saldo.empty:
        saldo_linha = primeira_linha_com_saldo["Saldo"].values[0]
        valor_linha = primeira_linha_com_saldo["Valor"].values[0]
        saldo_inicial = saldo_linha - valor_linha

    df["Saldo"] = (saldo_inicial + df["Valor"].cumsum()).round(2)
    return df


def consolidar_extratos(dataframes: list[pd.DataFrame]) -> pd.DataFrame:
    """
    Consolida múltiplos DataFrames em um único, removendo duplicatas.

    Args:
        dataframes: Lista de DataFrames processados.

    Returns:
        DataFrame consolidado e ordenado cronologicamente.
    """
    df_final = pd.concat(dataframes, ignore_index=True)

    df_final = df_final.drop_duplicates(
        subset=["Data", "Historico", "Documento", "Valor"], keep="first"
    )

    df_final["Ordem_Tipo"] = np.where(df_final["Valor"] >= 0, 0, 1)
    df_final = df_final.sort_values(by=["Data", "Ordem_Tipo"], ascending=[True, True])
    df_final = df_final.drop(columns=["Ordem_Tipo"])

    df_final = recalcular_saldo(df_final)

    return df_final


def processar_arquivos_paralelo(arquivos: list[Path]) -> list[pd.DataFrame]:
    """
    Processa múltiplos arquivos em paralelo usando ProcessPoolExecutor.

    Args:
        arquivos: Lista de caminhos para arquivos XLS.

    Returns:
        Lista de DataFrames processados com sucesso.
    """
    resultados: list[pd.DataFrame] = []

    with ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(processar_arquivo_bradesco, arq): arq for arq in arquivos
        }

        for future in as_completed(futures):
            arquivo = futures[future]
            try:
                resultado = future.result()
                if resultado is not None and not resultado.empty:
                    resultados.append(resultado)
            except Exception as e:
                logger.error(f"Error processing {arquivo.name}: {e}")

    return resultados


def processar_extratos() -> pd.DataFrame | None:
    """
    Função principal para processar todos os extratos da pasta.

    Returns:
        DataFrame consolidado ou None se não houver dados.
    """
    if not PASTA_EXTRATOS.exists():
        PASTA_EXTRATOS.mkdir(parents=True, exist_ok=True)
        logger.info("Folder created. Add XLS files to data/extratos/")
        return None

    arquivos = list(PASTA_EXTRATOS.glob("*.xls*"))
    if not arquivos:
        logger.warning("No files found in data/extratos/")
        return None

    logger.info(f"Processing {len(arquivos)} files...")

    todos_dados = processar_arquivos_paralelo(arquivos)

    if not todos_dados:
        logger.warning("No valid data found.")
        return None

    df_final = consolidar_extratos(todos_dados)

    try:
        df_final.to_csv(
            ARQUIVO_SAIDA, index=False, sep=SEPARADOR_CSV, decimal=DECIMAL_CSV
        )
        logger.info("SUCCESS! Balances recalculated and corrected.")
        logger.info(f"Output file: {ARQUIVO_SAIDA}")
    except PermissionError:
        logger.error("CLOSE THE CSV FILE BEFORE RUNNING!")
        return None

    return df_final


# =============================================================================
# FUNÇÕES - DASHBOARD
# =============================================================================
def preparar_dados_dashboard(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adiciona colunas calculadas necessárias para o dashboard.

    Args:
        df: DataFrame consolidado dos extratos.

    Returns:
        DataFrame com colunas adicionais para análise.
    """
    df = df.copy()
    df["Data"] = pd.to_datetime(df["Data"])
    df["Ano"] = df["Data"].dt.year
    df["Mes"] = df["Data"].dt.month
    df["AnoMes"] = df["Data"].dt.strftime("%Y-%m")
    df["MesNome"] = df["Data"].dt.strftime("%b/%Y")
    df["Tipo"] = df["Valor"].apply(lambda x: "Crédito" if x >= 0 else "Débito")
    df["Credito_Abs"] = df["Credito"].abs()
    df["Debito_Abs"] = df["Debito"].abs()

    return df


def criar_pagina_visao_geral(dashboard: Any, data_source: str) -> None:
    """
    Cria a página de Visão Geral com KPIs e gráficos principais.

    Args:
        dashboard: Instância do Dashboard powerbpy.
        data_source: Nome do dataset no dashboard.
    """
    page = dashboard.new_page(page_name="Visão Geral")

    cards_y = 20
    card_spacing = 20

    # Card 1: Saldo Atual
    page.add_card(
        visual_id="card_saldo",
        data_source=data_source,
        measure_name="Saldo",
        card_title="Saldo Atual",
        x_position=20,
        y_position=cards_y,
        height=CARD_HEIGHT,
        width=CARD_WIDTH,
        font_size=32,
        font_color=CORES["primary"],
        background_color=CORES["background"],
    )

    # Card 2: Total Créditos
    page.add_card(
        visual_id="card_creditos",
        data_source=data_source,
        measure_name="Credito_Abs",
        card_title="Total Créditos",
        x_position=20 + CARD_WIDTH + card_spacing,
        y_position=cards_y,
        height=CARD_HEIGHT,
        width=CARD_WIDTH,
        font_size=32,
        font_color=CORES["success"],
        background_color=CORES["background"],
    )

    # Card 3: Total Débitos
    page.add_card(
        visual_id="card_debitos",
        data_source=data_source,
        measure_name="Debito_Abs",
        card_title="Total Débitos",
        x_position=20 + (CARD_WIDTH + card_spacing) * 2,
        y_position=cards_y,
        height=CARD_HEIGHT,
        width=CARD_WIDTH,
        font_size=32,
        font_color=CORES["danger"],
        background_color=CORES["background"],
    )

    # Card 4: Número de Transações
    page.add_card(
        visual_id="card_transacoes",
        data_source=data_source,
        measure_name="TransactionID",
        card_title="Nº Transações",
        x_position=20 + (CARD_WIDTH + card_spacing) * 3,
        y_position=cards_y,
        height=CARD_HEIGHT,
        width=CARD_WIDTH,
        font_size=32,
        font_color=CORES["dark"],
        background_color=CORES["background"],
    )

    charts_y = cards_y + CARD_HEIGHT + 30
    chart_width = (CANVAS_WIDTH - 60) // 2

    # Gráfico: Evolução do Saldo
    page.add_chart(
        visual_id="chart_evolucao_saldo",
        chart_type="columnChart",
        data_source=data_source,
        chart_title="Evolução do Saldo por Mês",
        x_axis_title="Mês",
        y_axis_title="Saldo (R$)",
        x_axis_var="AnoMes",
        y_axis_var="Saldo",
        y_axis_var_aggregation_type="Average",
        x_position=20,
        y_position=charts_y,
        height=CHART_HEIGHT,
        width=chart_width,
        background_color=CORES["white"],
    )

    # Gráfico: Créditos vs Débitos
    page.add_chart(
        visual_id="chart_credito_debito",
        chart_type="clusteredBarChart",
        data_source=data_source,
        chart_title="Créditos vs Débitos por Mês",
        x_axis_title="Valor (R$)",
        y_axis_title="Mês",
        x_axis_var="Valor",
        y_axis_var="AnoMes",
        y_axis_var_aggregation_type="Sum",
        x_position=40 + chart_width,
        y_position=charts_y,
        height=CHART_HEIGHT,
        width=chart_width,
        background_color=CORES["white"],
    )

    table_y = charts_y + CHART_HEIGHT + 30

    # Tabela: Últimas Transações
    page.add_table(
        visual_id="table_transacoes_recentes",
        data_source=data_source,
        variables=["Data", "Historico", "Credito", "Debito", "Saldo"],
        table_title="Últimas Transações",
        x_position=20,
        y_position=table_y,
        height=TABLE_HEIGHT,
        width=CANVAS_WIDTH - 40,
        add_totals_row=True,
        background_color=CORES["white"],
    )

    logger.info("Page 'Visão Geral' created: 4 KPI cards, 2 charts, 1 table")


def criar_pagina_analise_mensal(dashboard: Any, data_source: str) -> None:
    """
    Cria a página de Análise Mensal com filtros e resumos.

    Args:
        dashboard: Instância do Dashboard powerbpy.
        data_source: Nome do dataset no dashboard.
    """
    page = dashboard.new_page(page_name="Análise Mensal")

    slicer_y = 20
    slicer_width = 200
    slicer_height = 150

    # Slicer: Ano
    page.add_slicer(
        visual_id="slicer_ano",
        data_source=data_source,
        column_name="Ano",
        title="Filtrar por Ano",
        x_position=20,
        y_position=slicer_y,
        height=slicer_height,
        width=slicer_width,
        background_color=CORES["background"],
    )

    # Slicer: Mês
    page.add_slicer(
        visual_id="slicer_mes",
        data_source=data_source,
        column_name="AnoMes",
        title="Filtrar por Mês",
        x_position=40 + slicer_width,
        y_position=slicer_y,
        height=slicer_height,
        width=slicer_width,
        background_color=CORES["background"],
    )

    # Slicer: Tipo
    page.add_slicer(
        visual_id="slicer_tipo",
        data_source=data_source,
        column_name="Tipo",
        title="Filtrar por Tipo",
        x_position=60 + slicer_width * 2,
        y_position=slicer_y,
        height=slicer_height,
        width=slicer_width,
        background_color=CORES["background"],
    )

    content_y = slicer_y + slicer_height + 30
    content_height = CANVAS_HEIGHT - content_y - 40
    chart_width = (CANVAS_WIDTH - 60) // 2

    # Gráfico: Fluxo de Caixa
    page.add_chart(
        visual_id="chart_fluxo_mensal",
        chart_type="columnChart",
        data_source=data_source,
        chart_title="Fluxo de Caixa Mensal",
        x_axis_title="Mês",
        y_axis_title="Valor (R$)",
        x_axis_var="AnoMes",
        y_axis_var="Valor",
        y_axis_var_aggregation_type="Sum",
        x_position=20,
        y_position=content_y,
        height=content_height,
        width=chart_width,
        background_color=CORES["white"],
    )

    # Tabela: Resumo Mensal
    page.add_table(
        visual_id="table_resumo_mensal",
        data_source=data_source,
        variables=["AnoMes", "Credito_Abs", "Debito_Abs", "Saldo"],
        table_title="Resumo por Mês",
        x_position=40 + chart_width,
        y_position=content_y,
        height=content_height,
        width=chart_width,
        add_totals_row=True,
        background_color=CORES["white"],
    )

    logger.info("Page 'Análise Mensal' created: 3 slicers, 1 chart, 1 table")


def criar_pagina_detalhamento(dashboard: Any, data_source: str) -> None:
    """
    Cria a página de Detalhamento com todas as transações.

    Args:
        dashboard: Instância do Dashboard powerbpy.
        data_source: Nome do dataset no dashboard.
    """
    page = dashboard.new_page(page_name="Detalhamento")

    slicer_y = 20
    slicer_width = 180
    slicer_height = 120

    # Slicer: Período
    page.add_slicer(
        visual_id="slicer_periodo",
        data_source=data_source,
        column_name="AnoMes",
        title="Período",
        x_position=20,
        y_position=slicer_y,
        height=slicer_height,
        width=slicer_width,
        background_color=CORES["background"],
    )

    # Slicer: Tipo
    page.add_slicer(
        visual_id="slicer_tipo_det",
        data_source=data_source,
        column_name="Tipo",
        title="Tipo",
        x_position=40 + slicer_width,
        y_position=slicer_y,
        height=slicer_height,
        width=slicer_width,
        background_color=CORES["background"],
    )

    table_y = slicer_y + slicer_height + 20
    table_height = CANVAS_HEIGHT - table_y - 20

    # Tabela: Todas as Transações
    page.add_table(
        visual_id="table_todas_transacoes",
        data_source=data_source,
        variables=[
            "Data",
            "Historico",
            "Documento",
            "Credito",
            "Debito",
            "Saldo",
            "Tipo",
            "AnoMes",
        ],
        table_title="Todas as Transações",
        x_position=20,
        y_position=table_y,
        height=table_height,
        width=CANVAS_WIDTH - 40,
        add_totals_row=True,
        background_color=CORES["white"],
    )

    logger.info("Page 'Detalhamento' created: 2 slicers, 1 full table")


def gerar_dashboard(df: pd.DataFrame) -> None:
    """
    Gera o dashboard Power BI a partir do DataFrame processado.

    Args:
        df: DataFrame consolidado dos extratos.
    """
    from powerbpy import Dashboard

    # Preparar dados para o dashboard
    df_dashboard = preparar_dados_dashboard(df)

    # Salvar CSV para o Power BI
    ARQUIVO_DASHBOARD_DATA.parent.mkdir(parents=True, exist_ok=True)
    df_dashboard.to_csv(ARQUIVO_DASHBOARD_DATA, index=False)
    logger.info(f"Dashboard data saved to: {ARQUIVO_DASHBOARD_DATA}")

    # Remover dashboard existente
    if DASHBOARD_PATH.exists():
        shutil.rmtree(DASHBOARD_PATH)
        logger.info(f"Removed existing dashboard at: {DASHBOARD_PATH}")

    # Criar estrutura
    DASHBOARD_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Criar dashboard
    logger.info(f"Creating dashboard at: {DASHBOARD_PATH}")
    dashboard = Dashboard.create(str(DASHBOARD_PATH))

    # Adicionar dados - o nome do dataset é derivado do nome do arquivo
    csv_dataset = dashboard.add_local_csv(str(ARQUIVO_DASHBOARD_DATA))
    data_source = csv_dataset.dataset_name
    logger.info(f"Dataset '{data_source}' added to dashboard")

    # Criar páginas
    criar_pagina_visao_geral(dashboard, data_source)
    criar_pagina_analise_mensal(dashboard, data_source)
    criar_pagina_detalhamento(dashboard, data_source)

    # Resumo final
    logger.info("=" * 60)
    logger.info("Dashboard created successfully!")
    logger.info("=" * 60)
    logger.info(f"Location: {DASHBOARD_PATH}")
    pbip_file = DASHBOARD_PATH / f"{DASHBOARD_PATH.name}.pbip"
    logger.info(f"Open file: {pbip_file}")
    logger.info("")
    logger.info("To view the dashboard:")
    logger.info("  1. Open Power BI Desktop")
    logger.info("  2. File > Open > Browse")
    logger.info(f"  3. Navigate to: {DASHBOARD_PATH}")
    logger.info(f"  4. Open: {pbip_file.name}")
    logger.info("=" * 60)


# =============================================================================
# MAIN
# =============================================================================
def main() -> None:
    df = processar_extratos()

    if df is None:
        return

    logger.info("")
    logger.info("=" * 60)
    logger.info("GENERATING POWER BI DASHBOARD")
    logger.info("=" * 60)
    gerar_dashboard(df)


if __name__ == "__main__":
    main()
