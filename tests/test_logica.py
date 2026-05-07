"""Pruebas unitarias de las funciones puras del prototipo.

Solo cubren `logica.py` (cálculos y operaciones determinísticas). La capa de UI
(`app.py`) y la descarga real con yfinance se validan manualmente con los
casos T1–T15 documentados en SPEC.md.
"""
from __future__ import annotations

import pandas as pd
import pytest

from logica import calcular_smas


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
