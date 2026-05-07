"""Fixtures compartidas para los tests UI con streamlit.testing.v1.AppTest.

Aislamos cada test en un directorio temporal para que la creación de
``usuarios.json`` y ``portafolio_<usuario>.json`` no contamine los datos del
usuario real. También añadimos la raíz del proyecto a ``sys.path`` para que
el script principal pueda importar ``logica`` aunque cambiemos el ``cwd``.
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

PROYECTO_RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROYECTO_RAIZ))

APP_PATH = str(PROYECTO_RAIZ / "app.py")


@pytest.fixture
def isolated_cwd(tmp_path, monkeypatch):
    """Cada test corre en un directorio temporal limpio."""
    monkeypatch.chdir(tmp_path)
    yield tmp_path


def _generar_ohlcv_sintetico(simbolo: str, start, end) -> pd.DataFrame:
    """OHLCV determinístico que pasa por todos los chequeos del prototipo.

    Tendencia ascendente suave con SMA20 cruzando por encima de la SMA50 al
    final del rango (debería disparar señal COMPRAR). Suficientes filas
    (>120) para que el RSI Wilder y las medias móviles sean significativos.
    """
    fechas = pd.date_range(start=start, end=end, freq="B")
    if len(fechas) < 60:
        # Asegura siempre al menos 120 días hábiles para SMA50 + buffer.
        fechas = pd.date_range(end=fechas[-1] if len(fechas) else "2026-05-01",
                               periods=180, freq="B")
    base = np.linspace(100, 200, len(fechas))
    ruido = np.sin(np.linspace(0, 8 * np.pi, len(fechas))) * 5
    cierre = base + ruido
    df = pd.DataFrame({
        "Open": cierre,
        "High": cierre * 1.005,
        "Low": cierre * 0.995,
        "Close": cierre,
        "Adj Close": cierre,
        "Volume": np.full(len(fechas), 1_000_000, dtype=int),
    }, index=fechas)
    # Replica el formato MultiIndex de yfinance para asegurar que la lógica
    # de aplanamiento en app.descargar_datos no se rompa.
    df.columns = pd.MultiIndex.from_product([df.columns, [simbolo]])
    return df


@pytest.fixture
def mock_yfinance():
    """Reemplaza ``yfinance.download`` con datos sintéticos determinísticos.

    Evita depender de la red en los tests UI. Se aplica como context manager
    porque AppTest carga app.py de nuevo en cada ``run()`` y el patch debe
    estar activo durante toda la ejecución del test.
    """
    def _fake_download(simbolo, start=None, end=None, **kwargs):
        # yfinance puede recibir lista de tickers; en nuestro código siempre es uno.
        sim = simbolo if isinstance(simbolo, str) else simbolo[0]
        return _generar_ohlcv_sintetico(sim, start, end)

    with patch("yfinance.download", side_effect=_fake_download) as p:
        yield p
