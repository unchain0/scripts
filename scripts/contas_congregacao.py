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
# CONSTANTES - CATEGORIZAÇÃO DE TRANSAÇÕES
# =============================================================================
CATEGORIAS_TRANSACOES = {
    "Doações/Depósitos": ["Dep Din Atm", "Deposito", "Dep Cheque"],
    "Remessas Organizacionais": ["Torre de Vigia", "Associacao Torre"],
    "Manutenção": ["Pagto Cobranca", "Manutencao", "Condominio", "Luz", "Agua"],
    "Rendimentos": ["Rendimentos Poup", "Rendimento", "Juros"],
    "Transferências": ["Transfe Pix", "Tr.aut.c/c", "Pix Enviado", "Pix Recebido"],
    "Recebimentos Especiais": ["Ted", "Receb Pagfor", "Doc"],
}
CATEGORIA_PADRAO = "Outros"

# =============================================================================
# CONSTANTES - DASHBOARD
# =============================================================================
CORES = {
    "primary": "#005A9E",
    "primary_light": "#0078D4",
    "accent": "#50E6FF",
    "background": "#FFFFFF",
    "background_alt": "#F8F9FA",
    "white": "#FFFFFF",
    "dark": "#2D3436",
    "text_muted": "#636E72",
}

DESCRICOES_VISUAIS: dict[str, str] = {
    "kpi_saldo": "Valor disponivel em caixa no momento",
    "kpi_creditos": "Soma de todas as entradas (doacoes, depositos, rendimentos)",
    "kpi_debitos": "Soma de todas as saidas (remessas, manutencao, despesas)",
    "kpi_transacoes": "Quantidade total de movimentacoes no periodo",
    "chart_evolucao_saldo": "Acompanhe como o saldo variou ao longo dos meses",
    "chart_credito_debito": "Compare entradas e saidas mensalmente",
    "table_transacoes_recentes": "Lista das ultimas movimentacoes registradas",
    "kpi_categoria_resumo": "Resumo das maiores fontes de receita e despesa",
    "chart_despesas_categoria": "Distribuicao percentual das saidas por tipo",
    "chart_receitas_categoria": "Distribuicao percentual das entradas por tipo",
    "table_categoria_detalhe": "Valores detalhados por categoria",
    "kpi_metricas_avancadas": "Indicadores financeiros para analise de saude fiscal",
    "chart_saldo_ma": "Tendencia do saldo com suavizacao de 3 meses",
    "chart_fluxo_ma": "Fluxo liquido (entradas - saidas) suavizado",
    "kpi_mom_growth": "Variacao percentual mes a mes",
    "chart_fluxo_mensal": "Saldo liquido de cada mes (positivo = sobrou, negativo = faltou)",
    "table_resumo_mensal": "Resumo consolidado por periodo",
    "table_todas_transacoes": "Listagem completa de todas as transacoes",
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
def categorizar_transacao(historico: str) -> str:
    """Categoriza uma transação baseado no campo Historico."""
    historico_upper = str(historico).upper()
    for categoria, palavras_chave in CATEGORIAS_TRANSACOES.items():
        for palavra in palavras_chave:
            if palavra.upper() in historico_upper:
                return categoria
    return CATEGORIA_PADRAO


def calcular_tendencia(valores: pd.Series) -> str:
    """Calcula tendência via regressão linear: 'Alta', 'Baixa' ou 'Estável'."""
    if len(valores) < 3:
        return "Estável"

    x = np.arange(len(valores))
    y = np.array(valores.values, dtype=float)

    slope, _ = np.polyfit(x, y, 1)

    std_y = float(np.std(y))
    threshold = std_y * 0.1 if std_y > 0 else 0.01

    if slope > threshold:
        return "Alta"
    elif slope < -threshold:
        return "Baixa"
    return "Estável"


def adicionar_moving_averages(df: pd.DataFrame) -> pd.DataFrame:
    """Adiciona médias móveis de 3 meses ao DataFrame."""
    df = df.copy()

    mensal = df.groupby("AnoMes").agg({"Saldo": "last", "Valor": "sum"}).reset_index()
    mensal["MA3_Saldo"] = mensal["Saldo"].rolling(window=3, min_periods=1).mean()
    mensal["MA3_Fluxo"] = mensal["Valor"].rolling(window=3, min_periods=1).mean()

    mensal["Tendencia"] = calcular_tendencia(mensal["Saldo"])

    ma_map = mensal.set_index("AnoMes")[
        ["MA3_Saldo", "MA3_Fluxo", "Tendencia"]
    ].to_dict()
    df["MA3_Saldo"] = df["AnoMes"].map(ma_map["MA3_Saldo"]).round(2)
    df["MA3_Fluxo"] = df["AnoMes"].map(ma_map["MA3_Fluxo"]).round(2)
    df["Tendencia"] = df["AnoMes"].map(ma_map["Tendencia"])

    return df


def detectar_anomalias(df: pd.DataFrame, threshold: float = 2.0) -> pd.DataFrame:
    """Detecta transações anômalas usando Z-Score por categoria."""
    df = df.copy()
    df["Anomalia"] = "Normal"

    for categoria in df["Categoria"].unique():
        cat_mask = df["Categoria"] == categoria
        cat_indices = df[cat_mask].index.tolist()

        if len(cat_indices) < 3:
            continue

        valores = df.loc[cat_indices, "Valor"].abs().astype(float)
        mean_val = valores.mean()
        std_val = valores.std()

        if std_val == 0:
            continue

        for idx in cat_indices:
            z_score = abs((abs(df.loc[idx, "Valor"]) - mean_val) / std_val)
            if z_score > threshold:
                df.loc[idx, "Anomalia"] = "Anomalia"

    return df


def calcular_metricas_avancadas(df: pd.DataFrame) -> dict[str, float]:
    """
    Calcula métricas financeiras avançadas.

    Retorna:
        savings_rate: Taxa de poupança (%)
        burn_rate: Taxa média mensal de gastos
        runway_meses: Meses de runway com saldo atual
        dias_caixa: Dias de caixa disponíveis
        income_expense_ratio: Razão receitas/despesas
        volatilidade: Volatilidade do fluxo mensal (%)
    """
    total_creditos = df["Credito_Abs"].sum()
    total_debitos = df["Debito_Abs"].sum()
    saldo_atual = df["Saldo"].iloc[-1] if not df.empty else 0.0

    savings_rate = 0.0
    if total_creditos > 0:
        savings_rate = ((total_creditos - total_debitos) / total_creditos) * 100

    fluxo_mensal = df.groupby("AnoMes")["Debito_Abs"].sum()
    burn_rate = fluxo_mensal.mean() if len(fluxo_mensal) > 0 else 0.0

    runway_meses = 999.0
    if burn_rate > 0:
        runway_meses = min(saldo_atual / burn_rate, 999.0)

    num_dias = (df["Data"].max() - df["Data"].min()).days + 1 if len(df) > 1 else 1
    dias_caixa = 999.0
    taxa_diaria = total_debitos / num_dias if num_dias > 0 else 0.0
    if taxa_diaria > 0:
        dias_caixa = min(saldo_atual / taxa_diaria, 999.0)

    income_expense_ratio = 0.0
    if total_debitos > 0:
        income_expense_ratio = total_creditos / total_debitos

    fluxo_liquido_mensal = df.groupby("AnoMes")["Valor"].sum()
    volatilidade = 0.0
    if len(fluxo_liquido_mensal) > 1 and fluxo_liquido_mensal.mean() != 0:
        volatilidade = (
            fluxo_liquido_mensal.std() / abs(fluxo_liquido_mensal.mean())
        ) * 100

    return {
        "savings_rate": round(savings_rate, 1),
        "burn_rate": round(burn_rate, 2),
        "runway_meses": round(runway_meses, 1),
        "dias_caixa": round(dias_caixa, 0),
        "income_expense_ratio": round(income_expense_ratio, 2),
        "volatilidade": round(volatilidade, 1),
    }


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
    df["Categoria"] = df["Historico"].apply(categorizar_transacao)

    df = adicionar_moving_averages(df)
    df = detectar_anomalias(df)

    return df


def _fix_chart_aggregation(dashboard_path: Path) -> None:
    """
    Corrige a agregação de gráficos no JSON do Power BI.

    A biblioteca powerbpy usa Function: 0 (Sum) por padrão, mas para gráficos
    como 'Evolução do Saldo', precisamos de Function: 1 (Average).
    """
    for visual_dir in dashboard_path.rglob("visuals"):
        for chart_dir in visual_dir.iterdir():
            if not chart_dir.is_dir():
                continue

            if "evolucao_saldo" not in chart_dir.name:
                continue

            visual_file = chart_dir / "visual.json"
            if not visual_file.exists():
                continue

            try:
                content = visual_file.read_text(encoding="utf-8")
                content_modified = content.replace('"Function": 0', '"Function": 1')
                if content_modified != content:
                    visual_file.write_text(content_modified, encoding="utf-8")
                    logger.info(f"Fixed aggregation to Average in {chart_dir.name}")
            except OSError as e:
                logger.warning(f"Failed to fix aggregation in {visual_file}: {e}")


def _fix_csv_encoding(dashboard_path: Path) -> None:
    """
    Corrige encoding (1252 -> 65001/UTF-8) e paths (backslash -> forward slash)
    nos arquivos .tmdl gerados pela powerbpy.
    """
    import re

    semantic_model_path = dashboard_path / f"{dashboard_path.name}.SemanticModel"
    tables_path = semantic_model_path / "definition" / "tables"

    if not tables_path.exists():
        logger.warning(f"Tables path not found: {tables_path}")
        return

    def fix_path(match: re.Match[str]) -> str:
        return f'File.Contents("{match.group(1).replace(chr(92), "/")}")'

    for tmdl_file in tables_path.glob("*.tmdl"):
        try:
            content = tmdl_file.read_text(encoding="utf-8")
            original_content = content

            content = content.replace("Encoding=1252", "Encoding=65001")
            content = re.sub(r'File\.Contents\("([^"]+)"\)', fix_path, content)

            if content != original_content:
                tmdl_file.write_text(content, encoding="utf-8")
                logger.info(f"Fixed CSV encoding and path in {tmdl_file.name}")
        except OSError as e:
            logger.warning(f"Failed to fix encoding in {tmdl_file}: {e}")


def _fix_visual_descriptions(dashboard_path: Path) -> None:
    """
    Adiciona subtítulos descritivos aos visuais do dashboard.

    Usa o dicionário DESCRICOES_VISUAIS para injetar descrições amigáveis
    em cada visual, ajudando usuários leigos a entender o propósito de cada
    gráfico ou KPI.
    """
    import json

    report_path = dashboard_path / f"{dashboard_path.name}.Report"
    pages_path = report_path / "definition" / "pages"

    if not pages_path.exists():
        logger.warning(f"Pages path not found: {pages_path}")
        return

    visuals_updated = 0

    for visual_dir in pages_path.rglob("visuals/*"):
        if not visual_dir.is_dir():
            continue

        visual_id = visual_dir.name
        if visual_id not in DESCRICOES_VISUAIS:
            continue

        visual_file = visual_dir / "visual.json"
        if not visual_file.exists():
            continue

        try:
            content = json.loads(visual_file.read_text(encoding="utf-8"))

            visual_container_objects = content.get("visual", {}).get(
                "visualContainerObjects", {}
            )

            description = DESCRICOES_VISUAIS[visual_id]
            subtitle_obj = [
                {
                    "properties": {
                        "show": {"expr": {"Literal": {"Value": "true"}}},
                        "text": {"expr": {"Literal": {"Value": f"'{description}'"}}},
                    }
                }
            ]

            visual_container_objects["subTitle"] = subtitle_obj

            visual_file.write_text(
                json.dumps(content, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            visuals_updated += 1

        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to add subtitle to {visual_id}: {e}")

    if visuals_updated > 0:
        logger.info(f"Added descriptions to {visuals_updated} visuals")


def _fix_theme_colors(dashboard_path: Path) -> None:
    """
    Atualiza as cores do tema do dashboard para a paleta azul minimalista.

    Modifica o arquivo de tema base para usar cores consistentes com o
    design branco + azul do dashboard.
    """
    import json

    theme_path = (
        dashboard_path
        / f"{dashboard_path.name}.Report"
        / "StaticResources"
        / "SharedResources"
        / "BaseThemes"
        / "CY24SU10.json"
    )

    if not theme_path.exists():
        logger.warning(f"Theme file not found: {theme_path}")
        return

    try:
        content = json.loads(theme_path.read_text(encoding="utf-8"))

        content["dataColors"] = [
            "#005A9E",
            "#0078D4",
            "#50E6FF",
            "#B3D9E6",
            "#E8F4F8",
        ]

        content["tableAccent"] = "#005A9E"
        content["foreground"] = "#2D3436"
        content["background"] = "#FFFFFF"

        theme_path.write_text(
            json.dumps(content, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        logger.info("Updated theme colors to blue palette")

    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Failed to update theme colors: {e}")


def _formatar_brl(valor: float) -> str:
    """Formata valor monetário no padrão brasileiro (R$ 1.234,56)."""
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def criar_pagina_visao_geral(
    dashboard: Any, data_source: str, df: pd.DataFrame
) -> None:
    """
    Cria a página de Visão Geral com KPIs e gráficos principais.

    Args:
        dashboard: Instância do Dashboard powerbpy.
        data_source: Nome do dataset no dashboard.
        df: DataFrame com os dados para calcular KPIs.
    """
    page = dashboard.new_page(page_name="Visão Geral")

    cards_y = 20
    card_spacing = 20

    saldo_atual = df["Saldo"].iloc[-1] if not df.empty else 0.0
    total_creditos = df["Credito_Abs"].sum() if "Credito_Abs" in df.columns else 0.0
    total_debitos = df["Debito_Abs"].sum() if "Debito_Abs" in df.columns else 0.0
    num_transacoes = len(df)

    page.add_text_box(
        visual_id="kpi_saldo",
        text=f"Saldo Atual\n{_formatar_brl(saldo_atual)}",
        x_position=20,
        y_position=cards_y,
        height=CARD_HEIGHT,
        width=CARD_WIDTH,
        font_size=24,
        font_color=CORES["primary"],
        background_color=CORES["background_alt"],
    )

    page.add_text_box(
        visual_id="kpi_creditos",
        text=f"Total Créditos\n{_formatar_brl(total_creditos)}",
        x_position=20 + CARD_WIDTH + card_spacing,
        y_position=cards_y,
        height=CARD_HEIGHT,
        width=CARD_WIDTH,
        font_size=24,
        font_color=CORES["primary_light"],
        background_color=CORES["background_alt"],
    )

    page.add_text_box(
        visual_id="kpi_debitos",
        text=f"Total Débitos\n{_formatar_brl(total_debitos)}",
        x_position=20 + (CARD_WIDTH + card_spacing) * 2,
        y_position=cards_y,
        height=CARD_HEIGHT,
        width=CARD_WIDTH,
        font_size=24,
        font_color=CORES["dark"],
        background_color=CORES["background_alt"],
    )

    page.add_text_box(
        visual_id="kpi_transacoes",
        text=f"Nº Transações\n{num_transacoes:,}".replace(",", "."),
        x_position=20 + (CARD_WIDTH + card_spacing) * 3,
        y_position=cards_y,
        height=CARD_HEIGHT,
        width=CARD_WIDTH,
        font_size=24,
        font_color=CORES["dark"],
        background_color=CORES["background_alt"],
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
        chart_type="clusteredColumnChart",
        data_source=data_source,
        chart_title="Créditos vs Débitos por Mês",
        x_axis_title="Mês",
        y_axis_title="Valor (R$)",
        x_axis_var="AnoMes",
        y_axis_var="Credito_Abs",
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
        background_color=CORES["background_alt"],
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
        background_color=CORES["background_alt"],
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
        background_color=CORES["background_alt"],
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


def criar_pagina_categoria(dashboard: Any, data_source: str, df: pd.DataFrame) -> None:
    """Cria a página de Análise por Categoria."""
    page = dashboard.new_page(page_name="Por Categoria")

    chart_height = 300
    chart_width = (CANVAS_WIDTH - 60) // 2

    debitos_por_cat = (
        df[df["Tipo"] == "Débito"].groupby("Categoria")["Debito_Abs"].sum()
    )
    creditos_por_cat = (
        df[df["Tipo"] == "Crédito"].groupby("Categoria")["Credito_Abs"].sum()
    )

    cat_resumo_text = "Resumo por Categoria\n\n"
    cat_resumo_text += "DESPESAS:\n"
    for cat, val in debitos_por_cat.sort_values(ascending=False).head(5).items():
        cat_resumo_text += f"  {cat}: {_formatar_brl(val)}\n"
    cat_resumo_text += "\nRECEITAS:\n"
    for cat, val in creditos_por_cat.sort_values(ascending=False).head(5).items():
        cat_resumo_text += f"  {cat}: {_formatar_brl(val)}\n"

    page.add_text_box(
        visual_id="kpi_categoria_resumo",
        text=cat_resumo_text,
        x_position=20,
        y_position=20,
        height=200,
        width=400,
        font_size=14,
        font_color=CORES["dark"],
        background_color=CORES["background_alt"],
    )

    page.add_chart(
        visual_id="chart_despesas_categoria",
        chart_type="donutChart",
        data_source=data_source,
        chart_title="Despesas por Categoria",
        x_axis_title="Categoria",
        y_axis_title="Valor (R$)",
        x_axis_var="Categoria",
        y_axis_var="Debito_Abs",
        y_axis_var_aggregation_type="Sum",
        x_position=20,
        y_position=240,
        height=chart_height,
        width=chart_width,
        background_color=CORES["white"],
    )

    page.add_chart(
        visual_id="chart_receitas_categoria",
        chart_type="donutChart",
        data_source=data_source,
        chart_title="Receitas por Categoria",
        x_axis_title="Categoria",
        y_axis_title="Valor (R$)",
        x_axis_var="Categoria",
        y_axis_var="Credito_Abs",
        y_axis_var_aggregation_type="Sum",
        x_position=40 + chart_width,
        y_position=240,
        height=chart_height,
        width=chart_width,
        background_color=CORES["white"],
    )

    page.add_table(
        visual_id="table_categoria_detalhe",
        data_source=data_source,
        variables=["Categoria", "Credito_Abs", "Debito_Abs"],
        table_title="Detalhamento por Categoria",
        x_position=440,
        y_position=20,
        height=200,
        width=CANVAS_WIDTH - 460,
        add_totals_row=True,
        background_color=CORES["white"],
    )

    logger.info("Page 'Por Categoria' created: 1 KPI, 2 donut charts, 1 table")


def criar_pagina_tendencias(dashboard: Any, data_source: str, df: pd.DataFrame) -> None:
    """Cria a página de Tendências e Métricas Avançadas."""
    page = dashboard.new_page(page_name="Tendências")

    metricas = calcular_metricas_avancadas(df)

    tendencia = df["Tendencia"].iloc[-1] if "Tendencia" in df.columns else "N/A"
    tendencia_emoji = (
        "↗" if tendencia == "Alta" else ("↘" if tendencia == "Baixa" else "→")
    )

    kpi_text = (
        f"Tendência Geral: {tendencia} {tendencia_emoji}\n\n"
        f"Taxa de Poupança: {metricas['savings_rate']:.1f}%\n"
        f"Burn Rate Mensal: {_formatar_brl(metricas['burn_rate'])}\n"
        f"Runway: {metricas['runway_meses']:.0f} meses\n"
        f"Dias de Caixa: {metricas['dias_caixa']:.0f}\n"
        f"Receita/Despesa: {metricas['income_expense_ratio']:.2f}x\n"
        f"Volatilidade: {metricas['volatilidade']:.1f}%"
    )

    page.add_text_box(
        visual_id="kpi_metricas_avancadas",
        text=kpi_text,
        x_position=20,
        y_position=20,
        height=200,
        width=350,
        font_size=16,
        font_color=CORES["primary"],
        background_color=CORES["background_alt"],
    )

    page.add_chart(
        visual_id="chart_saldo_ma",
        chart_type="lineChart",
        data_source=data_source,
        chart_title="Saldo com Média Móvel (3 meses)",
        x_axis_title="Mês",
        y_axis_title="Saldo (R$)",
        x_axis_var="AnoMes",
        y_axis_var="MA3_Saldo",
        y_axis_var_aggregation_type="Average",
        x_position=390,
        y_position=20,
        height=200,
        width=CANVAS_WIDTH - 410,
        background_color=CORES["white"],
    )

    page.add_chart(
        visual_id="chart_fluxo_ma",
        chart_type="columnChart",
        data_source=data_source,
        chart_title="Fluxo Líquido com Média Móvel (3 meses)",
        x_axis_title="Mês",
        y_axis_title="Valor (R$)",
        x_axis_var="AnoMes",
        y_axis_var="MA3_Fluxo",
        y_axis_var_aggregation_type="Average",
        x_position=20,
        y_position=240,
        height=280,
        width=(CANVAS_WIDTH - 60) // 2,
        background_color=CORES["white"],
    )

    mensal = df.groupby("AnoMes").agg({"Valor": "sum"}).reset_index()
    mensal["MoM_Growth"] = mensal["Valor"].pct_change() * 100

    mom_text = "Crescimento MoM (últimos 6 meses):\n\n"
    for _, row in mensal.tail(6).iterrows():
        growth = row["MoM_Growth"]
        if pd.notna(growth):
            sinal = "+" if growth >= 0 else ""
            mom_text += f"{row['AnoMes']}: {sinal}{growth:.1f}%\n"
        else:
            mom_text += f"{row['AnoMes']}: N/A\n"

    page.add_text_box(
        visual_id="kpi_mom_growth",
        text=mom_text,
        x_position=40 + (CANVAS_WIDTH - 60) // 2,
        y_position=240,
        height=280,
        width=(CANVAS_WIDTH - 60) // 2,
        font_size=14,
        font_color=CORES["dark"],
        background_color=CORES["background_alt"],
    )

    logger.info("Page 'Tendências' created: 2 KPIs, 2 charts")


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
        background_color=CORES["background_alt"],
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
        background_color=CORES["background_alt"],
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
            "Categoria",
            "Credito",
            "Debito",
            "Saldo",
            "Tipo",
            "Anomalia",
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
    criar_pagina_visao_geral(dashboard, data_source, df_dashboard)
    criar_pagina_categoria(dashboard, data_source, df_dashboard)
    criar_pagina_tendencias(dashboard, data_source, df_dashboard)
    criar_pagina_analise_mensal(dashboard, data_source)
    criar_pagina_detalhamento(dashboard, data_source)

    _fix_chart_aggregation(DASHBOARD_PATH)
    _fix_csv_encoding(DASHBOARD_PATH)
    _fix_visual_descriptions(DASHBOARD_PATH)
    _fix_theme_colors(DASHBOARD_PATH)

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
