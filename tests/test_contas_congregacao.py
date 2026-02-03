import json
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from scripts.contas_congregacao import (
    _fix_chart_aggregation,
    _formatar_brl,
    _inject_mobile_layout,
    limpar_numero,
    preparar_dados_dashboard,
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


class TestInjectMobileLayout:
    def test_injeta_mobile_state_em_page_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            page_dir = Path(tmpdir) / "pages" / "page1"
            page_dir.mkdir(parents=True)
            visuals_dir = page_dir / "visuals" / "visual1"
            visuals_dir.mkdir(parents=True)

            page_file = page_dir / "page.json"
            page_file.write_text(json.dumps({"name": "page1"}))

            visual_file = visuals_dir / "visual.json"
            visual_file.write_text(
                json.dumps({"name": "visual1", "position": {"height": 100}})
            )

            _inject_mobile_layout(Path(tmpdir))

            data = json.loads(page_file.read_text())
            assert "mobileState" in data
            assert "visualContainers" in data["mobileState"]
            assert data["mobileState"]["width"] == 320

    def test_ignora_pagina_sem_visuals(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            page_dir = Path(tmpdir) / "pages" / "page1"
            page_dir.mkdir(parents=True)

            page_file = page_dir / "page.json"
            original_content = json.dumps({"name": "Empty Page"})
            page_file.write_text(original_content)

            _inject_mobile_layout(Path(tmpdir))

            data = json.loads(page_file.read_text())
            assert "mobileState" not in data
