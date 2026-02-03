import json
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from scripts.contas_congregacao import (
    _fix_chart_aggregation,
    _fix_csv_encoding,
    _fix_theme_colors,
    _fix_visual_descriptions,
    _formatar_brl,
    adicionar_moving_averages,
    calcular_metricas_avancadas,
    calcular_tendencia,
    categorizar_transacao,
    detectar_anomalias,
    limpar_numero,
    preparar_dados_dashboard,
    DESCRICOES_VISUAIS,
)


class TestLimparNumero:
    def test_numero_brasileiro(self):
        assert limpar_numero("1.234,56") == 1234.56

    def test_numero_negativo(self):
        assert limpar_numero("-1.000,00") == -1000.0

    def test_valor_vazio(self):
        assert limpar_numero("") == 0.0

    def test_valor_traco(self):
        assert limpar_numero("-") == 0.0

    def test_valor_nan(self):
        assert limpar_numero(float("nan")) == 0.0


class TestFormatarBrl:
    def test_valor_positivo(self):
        assert _formatar_brl(1234.56) == "R$ 1.234,56"

    def test_valor_grande(self):
        assert _formatar_brl(1000000.00) == "R$ 1.000.000,00"

    def test_valor_zero(self):
        assert _formatar_brl(0) == "R$ 0,00"


class TestPrepararDadosDashboard:
    @pytest.fixture
    def df_extrato(self):
        return pd.DataFrame(
            {
                "Data": pd.to_datetime(["2024-01-15", "2024-02-20"]),
                "Historico": ["Deposito", "Saque"],
                "Documento": ["123", "456"],
                "Credito": [1000.0, 0.0],
                "Debito": [0.0, -500.0],
                "Saldo": [1000.0, 500.0],
                "Valor": [1000.0, -500.0],
                "Arquivo_Origem": ["extrato.xls", "extrato.xls"],
            }
        )

    def test_adiciona_colunas_temporais(self, df_extrato):
        result = preparar_dados_dashboard(df_extrato)

        assert "Ano" in result.columns
        assert "Mes" in result.columns
        assert "AnoMes" in result.columns
        assert "MesNome" in result.columns

    def test_adiciona_coluna_tipo(self, df_extrato):
        result = preparar_dados_dashboard(df_extrato)

        assert "Tipo" in result.columns
        assert result.iloc[0]["Tipo"] == "Crédito"
        assert result.iloc[1]["Tipo"] == "Débito"

    def test_adiciona_valores_absolutos(self, df_extrato):
        result = preparar_dados_dashboard(df_extrato)

        assert "Credito_Abs" in result.columns
        assert "Debito_Abs" in result.columns
        assert result["Credito_Abs"].iloc[0] == 1000.0
        assert result["Debito_Abs"].iloc[1] == 500.0


class TestFixChartAggregation:
    def test_corrige_aggregation_em_visual_evolucao_saldo(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            visuals_dir = Path(tmpdir) / "visuals" / "chart_evolucao_saldo"
            visuals_dir.mkdir(parents=True)
            visual_file = visuals_dir / "visual.json"
            visual_file.write_text('{"name": "chart_evolucao_saldo", "Function": 0}')

            _fix_chart_aggregation(Path(tmpdir))

            content = visual_file.read_text()
            assert '"Function": 1' in content

    def test_ignora_outros_visuais(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            visuals_dir = Path(tmpdir) / "visuals" / "chart_outro"
            visuals_dir.mkdir(parents=True)
            visual_file = visuals_dir / "visual.json"
            original_content = '{"name": "chart_outro", "Function": 0}'
            visual_file.write_text(original_content)

            _fix_chart_aggregation(Path(tmpdir))

            assert visual_file.read_text() == original_content


class TestFixCsvEncoding:
    def test_corrige_encoding_1252_para_65001(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            dashboard_path = Path(tmpdir) / "Dashboard"
            dashboard_path.mkdir()
            tables_dir = (
                dashboard_path / "Dashboard.SemanticModel" / "definition" / "tables"
            )
            tables_dir.mkdir(parents=True)
            tmdl_file = tables_dir / "Data.tmdl"
            original = 'Source = Csv.Document(File.Contents("\\path\\to\\file.csv"),[Encoding=1252])'
            tmdl_file.write_text(original, encoding="utf-8")

            _fix_csv_encoding(dashboard_path)

            content = tmdl_file.read_text(encoding="utf-8")
            assert "Encoding=65001" in content
            assert "/path/to/file.csv" in content

    def test_nao_altera_se_ja_correto(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            dashboard_path = Path(tmpdir) / "Dashboard"
            dashboard_path.mkdir()
            tables_dir = (
                dashboard_path / "Dashboard.SemanticModel" / "definition" / "tables"
            )
            tables_dir.mkdir(parents=True)
            tmdl_file = tables_dir / "Data.tmdl"
            original = 'Source = Csv.Document(File.Contents("/path/to/file.csv"),[Encoding=65001])'
            tmdl_file.write_text(original, encoding="utf-8")

            _fix_csv_encoding(dashboard_path)

            assert tmdl_file.read_text(encoding="utf-8") == original


class TestCategorizarTransacao:
    def test_deposito_atm(self):
        assert categorizar_transacao("Dep Din Atm Agencia 1234") == "Doações/Depósitos"

    def test_torre_de_vigia(self):
        assert (
            categorizar_transacao("Transf.para c/c Associacao Torre de Vigia")
            == "Remessas Organizacionais"
        )

    def test_pagamento_cobranca(self):
        assert categorizar_transacao("Pagto Cobranca Celesc") == "Manutenção"

    def test_rendimentos(self):
        assert categorizar_transacao("Rendimentos Poup 01/2024") == "Rendimentos"

    def test_pix(self):
        assert categorizar_transacao("Transfe Pix Fulano") == "Transferências"

    def test_ted(self):
        assert categorizar_transacao("Ted Recebido") == "Recebimentos Especiais"

    def test_outros(self):
        assert categorizar_transacao("Operação desconhecida") == "Outros"


class TestCalcularMetricasAvancadas:
    @pytest.fixture
    def df_metricas(self):
        return pd.DataFrame(
            {
                "Data": pd.to_datetime(
                    ["2024-01-15", "2024-01-20", "2024-02-15", "2024-02-20"]
                ),
                "Credito_Abs": [1000.0, 500.0, 800.0, 200.0],
                "Debito_Abs": [300.0, 100.0, 400.0, 100.0],
                "Saldo": [700.0, 1100.0, 1500.0, 1600.0],
                "Valor": [700.0, 400.0, 400.0, 100.0],
                "AnoMes": ["2024-01", "2024-01", "2024-02", "2024-02"],
            }
        )

    def test_savings_rate_positivo(self, df_metricas):
        metricas = calcular_metricas_avancadas(df_metricas)
        assert metricas["savings_rate"] > 0

    def test_burn_rate_calculado(self, df_metricas):
        metricas = calcular_metricas_avancadas(df_metricas)
        assert metricas["burn_rate"] > 0

    def test_income_expense_ratio(self, df_metricas):
        metricas = calcular_metricas_avancadas(df_metricas)
        total_creditos = df_metricas["Credito_Abs"].sum()
        total_debitos = df_metricas["Debito_Abs"].sum()
        expected = total_creditos / total_debitos
        assert abs(metricas["income_expense_ratio"] - expected) < 0.01


class TestCalcularTendencia:
    def test_tendencia_alta(self):
        valores = pd.Series([100, 200, 300, 400, 500])
        assert calcular_tendencia(valores) == "Alta"

    def test_tendencia_baixa(self):
        valores = pd.Series([500, 400, 300, 200, 100])
        assert calcular_tendencia(valores) == "Baixa"

    def test_tendencia_estavel(self):
        valores = pd.Series([100, 100, 100, 100, 100])
        assert calcular_tendencia(valores) == "Estável"

    def test_poucos_valores(self):
        valores = pd.Series([100, 200])
        assert calcular_tendencia(valores) == "Estável"


class TestAdicionarMovingAverages:
    @pytest.fixture
    def df_mensal(self):
        return pd.DataFrame(
            {
                "Data": pd.to_datetime(
                    ["2024-01-15", "2024-02-15", "2024-03-15", "2024-04-15"]
                ),
                "Saldo": [1000.0, 1200.0, 1400.0, 1600.0],
                "Valor": [100.0, 200.0, 200.0, 200.0],
                "AnoMes": ["2024-01", "2024-02", "2024-03", "2024-04"],
            }
        )

    def test_adiciona_colunas_ma(self, df_mensal):
        result = adicionar_moving_averages(df_mensal)
        assert "MA3_Saldo" in result.columns
        assert "MA3_Fluxo" in result.columns
        assert "Tendencia" in result.columns


class TestDetectarAnomalias:
    @pytest.fixture
    def df_anomalia(self):
        df = pd.DataFrame(
            {
                "Valor": [100.0, 110.0, 105.0, 95.0, 100.0, 5000.0],
                "Categoria": ["A", "A", "A", "A", "A", "A"],
            }
        )
        return df

    def test_detecta_valor_anomalo(self, df_anomalia):
        result = detectar_anomalias(df_anomalia, threshold=2.0)
        assert "Anomalia" in result.columns
        assert result[result["Valor"] == 5000.0]["Anomalia"].iloc[0] == "Anomalia"

    def test_valores_normais(self, df_anomalia):
        result = detectar_anomalias(df_anomalia)
        normais = result[result["Valor"] < 200]["Anomalia"]
        assert all(n == "Normal" for n in normais)


class TestFixVisualDescriptions:
    def test_adiciona_subtitle_em_visual_conhecido(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            dashboard_path = Path(tmpdir) / "Dashboard"
            visual_dir = (
                dashboard_path
                / "Dashboard.Report"
                / "definition"
                / "pages"
                / "page1"
                / "visuals"
                / "kpi_saldo"
            )
            visual_dir.mkdir(parents=True)
            visual_file = visual_dir / "visual.json"
            original = {
                "name": "kpi_saldo",
                "visual": {"visualContainerObjects": {"title": []}},
            }
            visual_file.write_text(json.dumps(original), encoding="utf-8")

            _fix_visual_descriptions(dashboard_path)

            content = json.loads(visual_file.read_text(encoding="utf-8"))
            assert "subTitle" in content["visual"]["visualContainerObjects"]
            subtitle = content["visual"]["visualContainerObjects"]["subTitle"]
            assert (
                subtitle[0]["properties"]["show"]["expr"]["Literal"]["Value"] == "true"
            )
            assert (
                DESCRICOES_VISUAIS["kpi_saldo"]
                in subtitle[0]["properties"]["text"]["expr"]["Literal"]["Value"]
            )

    def test_ignora_visual_desconhecido(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            dashboard_path = Path(tmpdir) / "Dashboard"
            visual_dir = (
                dashboard_path
                / "Dashboard.Report"
                / "definition"
                / "pages"
                / "page1"
                / "visuals"
                / "visual_desconhecido"
            )
            visual_dir.mkdir(parents=True)
            visual_file = visual_dir / "visual.json"
            original = {
                "name": "visual_desconhecido",
                "visual": {"visualContainerObjects": {}},
            }
            visual_file.write_text(json.dumps(original), encoding="utf-8")

            _fix_visual_descriptions(dashboard_path)

            content = json.loads(visual_file.read_text(encoding="utf-8"))
            assert "subTitle" not in content["visual"]["visualContainerObjects"]


class TestFixThemeColors:
    def test_atualiza_cores_do_tema(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            dashboard_path = Path(tmpdir) / "Dashboard"
            theme_dir = (
                dashboard_path
                / "Dashboard.Report"
                / "StaticResources"
                / "SharedResources"
                / "BaseThemes"
            )
            theme_dir.mkdir(parents=True)
            theme_file = theme_dir / "CY24SU10.json"
            original = {
                "name": "theme",
                "dataColors": ["#FF0000", "#00FF00"],
                "tableAccent": "#000000",
                "foreground": "#000000",
                "background": "#000000",
            }
            theme_file.write_text(json.dumps(original), encoding="utf-8")

            _fix_theme_colors(dashboard_path)

            content = json.loads(theme_file.read_text(encoding="utf-8"))
            assert content["dataColors"][0] == "#005A9E"
            assert content["tableAccent"] == "#005A9E"
            assert content["foreground"] == "#2D3436"
            assert content["background"] == "#FFFFFF"

    def test_nao_falha_se_tema_nao_existe(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            dashboard_path = Path(tmpdir) / "Dashboard"
            dashboard_path.mkdir()

            _fix_theme_colors(dashboard_path)
