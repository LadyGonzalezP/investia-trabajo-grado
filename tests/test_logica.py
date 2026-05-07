"""Pruebas unitarias de las funciones puras del prototipo.

Solo cubren `logica.py` (cálculos y operaciones determinísticas). La capa de UI
(`app.py`) y la descarga real con yfinance se validan manualmente con los
casos T1–T15 documentados en SPEC.md.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from logica import (
    SALDO_INICIAL_USD,
    calcular_metricas,
    calcular_rsi,
    calcular_smas,
    cargar_portafolio,
    generar_senal,
    guardar_portafolio,
)


# ---------------------------------------------------------------------------
# T1 — SMA
# ---------------------------------------------------------------------------

def test_sma_calcula_promedio_ventana() -> None:
    """SMA_n en el índice n-1 debe ser el promedio aritmético simple."""
    df = pd.DataFrame({"Close": [10.0, 20.0, 30.0, 40.0, 50.0]})

    resultado = calcular_smas(df, ventanas=(3, 5))

    # SMA de ventana 3 en índice 2 = (10+20+30)/3 = 20
    assert resultado["SMA_3"].iloc[2] == pytest.approx(20.0)
    # SMA de ventana 5 en índice 4 = (10+20+30+40+50)/5 = 30
    assert resultado["SMA_5"].iloc[4] == pytest.approx(30.0)


def test_sma_devuelve_nan_antes_de_completar_ventana() -> None:
    """Antes de cumplirse la ventana no hay datos suficientes -> NaN."""
    df = pd.DataFrame({"Close": list(range(1, 11))})  # solo 10 filas

    resultado = calcular_smas(df, ventanas=(20, 50))

    assert resultado["SMA_20"].isna().all()
    assert resultado["SMA_50"].isna().all()


# ---------------------------------------------------------------------------
# T2 — RSI (Wilder)
# ---------------------------------------------------------------------------

def test_rsi_valor_conocido_serie_creciente() -> None:
    """En una serie estrictamente creciente no hay pérdidas -> RSI tiende a 100."""
    serie = pd.Series([float(x) for x in range(1, 31)])

    rsi = calcular_rsi(serie, periodo=14)

    assert rsi.iloc[-1] == pytest.approx(100.0)


def test_rsi_serie_decreciente_aproxima_cero() -> None:
    """En una serie estrictamente decreciente no hay ganancias -> RSI tiende a 0."""
    serie = pd.Series([float(x) for x in range(30, 0, -1)])

    rsi = calcular_rsi(serie, periodo=14)

    assert rsi.iloc[-1] == pytest.approx(0.0)


def test_rsi_longitud_insuficiente_devuelve_nan() -> None:
    """Con menos filas que el periodo no hay datos suficientes -> todo NaN."""
    serie = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])

    rsi = calcular_rsi(serie, periodo=14)

    assert rsi.isna().all()


# ---------------------------------------------------------------------------
# T3 — Señal educativa
# ---------------------------------------------------------------------------

def _df_indicadores(sma20: float, sma50: float, rsi: float) -> pd.DataFrame:
    """Construye un DataFrame mínimo con los valores finales necesarios."""
    return pd.DataFrame(
        {
            "SMA_20": [float("nan"), sma20],
            "SMA_50": [float("nan"), sma50],
            "RSI_14": [float("nan"), rsi],
        }
    )


def test_senal_comprar_cuando_sma20_supera_sma50_y_rsi_bajo() -> None:
    df = _df_indicadores(sma20=105.0, sma50=100.0, rsi=55.0)

    senal, motivo = generar_senal(df)

    assert senal == "COMPRAR"
    # El motivo debe ser explicativo y citar valores numéricos.
    assert "105" in motivo and "100" in motivo


def test_senal_vender_cuando_sma20_bajo_sma50() -> None:
    df = _df_indicadores(sma20=95.0, sma50=100.0, rsi=50.0)

    senal, motivo = generar_senal(df)

    assert senal == "VENDER"
    assert "95" in motivo


def test_senal_vender_cuando_rsi_sobrecomprado() -> None:
    df = _df_indicadores(sma20=110.0, sma50=100.0, rsi=75.0)

    senal, motivo = generar_senal(df)

    assert senal == "VENDER"
    assert "75" in motivo


def test_senal_mantener_caso_neutro() -> None:
    """SMA20 == SMA50 y RSI moderado: ninguna condición clara."""
    df = _df_indicadores(sma20=100.0, sma50=100.0, rsi=50.0)

    senal, _ = generar_senal(df)

    assert senal == "MANTENER"


# ---------------------------------------------------------------------------
# T4 — Métricas
# ---------------------------------------------------------------------------

def test_metricas_calcula_variacion_y_volatilidad() -> None:
    closes = [100.0, 102.0, 101.0, 103.0, 110.0]
    df = pd.DataFrame({"Close": closes})

    metricas = calcular_metricas(df)

    assert metricas["precio_actual"] == pytest.approx(110.0)
    assert metricas["variacion_pct"] == pytest.approx(10.0)  # (110/100 - 1) * 100
    assert metricas["stop_loss"] == pytest.approx(110.0 * 0.95)
    assert metricas["take_profit"] == pytest.approx(110.0 * 1.10)

    pct = pd.Series(closes).pct_change().dropna()
    esperada = pct.std() * np.sqrt(252) * 100
    assert metricas["volatilidad_anual_pct"] == pytest.approx(esperada)


# ---------------------------------------------------------------------------
# T5 — Persistencia del portafolio
# ---------------------------------------------------------------------------

def test_cargar_portafolio_inexistente_devuelve_estado_inicial(tmp_path) -> None:
    """Si el archivo no existe, se entrega el estado inicial vacío."""
    ruta = tmp_path / "portafolio.json"

    estado = cargar_portafolio(ruta)

    assert estado == {"saldo_usd": SALDO_INICIAL_USD, "transacciones": []}


def test_guardar_y_cargar_es_idempotente(tmp_path) -> None:
    """Guardar un estado y volverlo a cargar debe devolver exactamente lo mismo."""
    ruta = tmp_path / "portafolio.json"
    estado = {
        "saldo_usd": 8125.50,
        "transacciones": [
            {
                "fecha": "2026-05-07",
                "simbolo": "AAPL",
                "tipo": "COMPRA",
                "cantidad": 10,
                "precio_unitario": 187.45,
            }
        ],
    }

    guardar_portafolio(ruta, estado)
    cargado = cargar_portafolio(ruta)

    assert cargado == estado
