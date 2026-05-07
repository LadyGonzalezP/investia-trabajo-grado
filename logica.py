"""Funciones puras del prototipo: indicadores técnicos, señales, métricas,
operaciones de portafolio y autenticación.

Este módulo NO depende de Streamlit ni hace I/O de red. Solo lectura/escritura
de archivos JSON locales (portafolio y usuarios). De este modo se puede testear
de forma determinística con pytest.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

import numpy as np
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


# ---------------------------------------------------------------------------
# Señal educativa
# ---------------------------------------------------------------------------

def generar_senal(df: pd.DataFrame) -> tuple[str, str]:
    """Genera una señal educativa COMPRAR/VENDER/MANTENER.

    Espera columnas ``SMA_20``, ``SMA_50`` y ``RSI_14`` ya calculadas. Toma la
    última fila donde las tres están definidas y aplica el criterio del SPEC:

    * ``COMPRAR`` si ``SMA_20 > SMA_50`` y ``RSI < 70``.
    * ``VENDER`` si ``SMA_20 < SMA_50`` o ``RSI > 70``.
    * ``MANTENER`` en cualquier otro caso.

    Devuelve ``(senal, motivo)``; el motivo cita los valores numéricos para que
    el usuario pueda entender la decisión.
    """
    fila = df[["SMA_20", "SMA_50", "RSI_14"]].dropna().iloc[-1]
    sma20, sma50, rsi = fila["SMA_20"], fila["SMA_50"], fila["RSI_14"]

    if sma20 > sma50 and rsi < 70:
        motivo = (
            f"SMA20 ({sma20:.2f}) supera a SMA50 ({sma50:.2f}) "
            f"y RSI={rsi:.1f} no está sobrecomprado."
        )
        return "COMPRAR", motivo

    if sma20 < sma50 or rsi > 70:
        razones: list[str] = []
        if sma20 < sma50:
            razones.append(
                f"SMA20 ({sma20:.2f}) por debajo de SMA50 ({sma50:.2f})"
            )
        if rsi > 70:
            razones.append(f"RSI={rsi:.1f} > 70 (sobrecompra)")
        return "VENDER", "; ".join(razones) + "."

    motivo = (
        f"SMA20 ({sma20:.2f}) ≈ SMA50 ({sma50:.2f}) "
        f"y RSI={rsi:.1f} en zona neutra."
    )
    return "MANTENER", motivo


# ---------------------------------------------------------------------------
# Métricas de portafolio individual
# ---------------------------------------------------------------------------

DIAS_HABILES_ANUALES = 252  # convención de finanzas para anualizar volatilidad

PORCENTAJE_STOP_LOSS = 0.95  # -5 % sobre el precio actual
PORCENTAJE_TAKE_PROFIT = 1.10  # +10 % sobre el precio actual


def calcular_metricas(df: pd.DataFrame) -> dict[str, float]:
    """Calcula KPIs descriptivos sobre el rango analizado.

    Devuelve un diccionario con claves estables:

    * ``precio_actual``: último cierre.
    * ``variacion_pct``: variación porcentual entre el primer y último cierre.
    * ``volatilidad_anual_pct``: desviación estándar de los retornos diarios
      anualizada (multiplicada por √252) y convertida a porcentaje.
    * ``stop_loss``: precio actual * 0.95.
    * ``take_profit``: precio actual * 1.10.
    """
    cierres = df["Close"]
    precio_actual = float(cierres.iloc[-1])
    precio_inicial = float(cierres.iloc[0])

    variacion_pct = (precio_actual / precio_inicial - 1) * 100

    retornos = cierres.pct_change().dropna()
    volatilidad_anual_pct = float(retornos.std() * np.sqrt(DIAS_HABILES_ANUALES) * 100)

    return {
        "precio_actual": precio_actual,
        "variacion_pct": variacion_pct,
        "volatilidad_anual_pct": volatilidad_anual_pct,
        "stop_loss": precio_actual * PORCENTAJE_STOP_LOSS,
        "take_profit": precio_actual * PORCENTAJE_TAKE_PROFIT,
    }


# ---------------------------------------------------------------------------
# Persistencia del portafolio
# ---------------------------------------------------------------------------

SALDO_INICIAL_USD = 10_000.0


def estado_inicial_portafolio() -> dict[str, Any]:
    """Estado de un portafolio recién creado para un usuario nuevo."""
    return {"saldo_usd": SALDO_INICIAL_USD, "transacciones": []}


def cargar_portafolio(ruta: str | Path) -> dict[str, Any]:
    """Lee el portafolio desde disco. Si no existe, devuelve el estado inicial."""
    ruta = Path(ruta)
    if not ruta.exists():
        return estado_inicial_portafolio()
    with ruta.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def guardar_portafolio(ruta: str | Path, estado: dict[str, Any]) -> None:
    """Persiste el portafolio en disco de forma atómica.

    Escribe a un archivo temporal y luego lo renombra: si el proceso muere a
    mitad de la escritura, el archivo destino mantiene su contenido anterior y
    no queda en estado corrupto.
    """
    ruta = Path(ruta)
    tmp = ruta.with_suffix(ruta.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(estado, fh, ensure_ascii=False, indent=2)
    tmp.replace(ruta)
