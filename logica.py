"""Funciones puras del prototipo: indicadores técnicos, señales, métricas,
operaciones de portafolio y autenticación.

Este módulo NO depende de Streamlit ni hace I/O de red. Solo lectura/escritura
de archivos JSON locales (portafolio y usuarios). De este modo se puede testear
de forma determinística con pytest.
"""
from __future__ import annotations

from typing import Iterable

import pandas as pd


# ---------------------------------------------------------------------------
# Indicadores técnicos
# ---------------------------------------------------------------------------

def calcular_smas(
    df: pd.DataFrame, ventanas: Iterable[int] = (20, 50)
) -> pd.DataFrame:
    """Añade columnas ``SMA_<ventana>`` con la media móvil simple de ``Close``.

    Devuelve una copia del DataFrame: nunca muta el argumento original (las
    funciones de la capa lógica son inmutables para evitar efectos colaterales
    al cachear con ``st.cache_data``).
    """
    resultado = df.copy()
    for ventana in ventanas:
        resultado[f"SMA_{ventana}"] = resultado["Close"].rolling(ventana).mean()
    return resultado


def calcular_rsi(serie: pd.Series, periodo: int = 14) -> pd.Series:
    """Índice de Fuerza Relativa (RSI) con suavizado tipo Wilder.

    Implementación: ganancias y pérdidas exponencialmente suavizadas con
    ``alpha = 1/periodo`` y ``adjust=False`` (equivalente práctico al método
    original de Wilder). Se requiere al menos ``periodo`` observaciones; antes
    de eso, el resultado es NaN.

    Casos límite:
    * Serie estrictamente creciente -> avg_perdida = 0 -> RSI = 100.
    * Serie estrictamente decreciente -> avg_ganancia = 0 -> RSI = 0.
    """
    delta = serie.diff()
    ganancia = delta.clip(lower=0)
    perdida = (-delta).clip(lower=0)

    # ewm con min_periods garantiza NaN hasta cumplirse la ventana inicial.
    avg_gan = ganancia.ewm(alpha=1 / periodo, min_periods=periodo, adjust=False).mean()
    avg_per = perdida.ewm(alpha=1 / periodo, min_periods=periodo, adjust=False).mean()

    rs = avg_gan / avg_per
    return 100 - 100 / (1 + rs)
