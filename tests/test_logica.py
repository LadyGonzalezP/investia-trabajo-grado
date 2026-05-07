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
    TransaccionInvalida,
    UsuarioYaExiste,
    aplicar_transaccion,
    calcular_metricas,
    calcular_rsi,
    calcular_smas,
    calcular_tenencias,
    cargar_portafolio,
    cargar_usuarios,
    generar_senal,
    guardar_portafolio,
    guardar_usuarios,
    hash_password,
    registrar_usuario,
    verificar_credenciales,
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


# ---------------------------------------------------------------------------
# T6 — Aplicar transacciones y tenencias
# ---------------------------------------------------------------------------

def _tx(simbolo: str, tipo: str, cantidad: int, precio: float, fecha: str = "2026-05-07") -> dict:
    return {
        "fecha": fecha,
        "simbolo": simbolo,
        "tipo": tipo,
        "cantidad": cantidad,
        "precio_unitario": precio,
    }


def test_aplicar_compra_descuenta_saldo_y_registra() -> None:
    estado = {"saldo_usd": 10000.0, "transacciones": []}

    nuevo = aplicar_transaccion(estado, _tx("AAPL", "COMPRA", 10, 187.45))

    # No debe mutar el estado original (función pura).
    assert estado["saldo_usd"] == 10000.0
    assert estado["transacciones"] == []

    assert nuevo["saldo_usd"] == pytest.approx(10000.0 - 1874.50)
    assert nuevo["transacciones"][0]["simbolo"] == "AAPL"


def test_aplicar_venta_suma_saldo() -> None:
    estado = aplicar_transaccion(
        {"saldo_usd": 10000.0, "transacciones": []},
        _tx("AAPL", "COMPRA", 10, 100.0),
    )

    nuevo = aplicar_transaccion(estado, _tx("AAPL", "VENTA", 5, 120.0))

    assert nuevo["saldo_usd"] == pytest.approx(10000.0 - 1000.0 + 600.0)
    assert len(nuevo["transacciones"]) == 2


def test_compra_excede_saldo_lanza_error() -> None:
    estado = {"saldo_usd": 100.0, "transacciones": []}

    with pytest.raises(TransaccionInvalida):
        aplicar_transaccion(estado, _tx("AAPL", "COMPRA", 10, 187.45))


def test_venta_excede_tenencia_lanza_error() -> None:
    estado = aplicar_transaccion(
        {"saldo_usd": 10000.0, "transacciones": []},
        _tx("AAPL", "COMPRA", 5, 100.0),
    )

    with pytest.raises(TransaccionInvalida):
        aplicar_transaccion(estado, _tx("AAPL", "VENTA", 10, 110.0))


def test_calcular_tenencias_neta_correctamente() -> None:
    """Promedio ponderado de costo + ventas que reducen cantidad sin cambiar promedio."""
    estado = {"saldo_usd": 5000.0, "transacciones": []}
    estado = aplicar_transaccion(estado, _tx("AAPL", "COMPRA", 10, 100.0))
    estado = aplicar_transaccion(estado, _tx("AAPL", "COMPRA", 10, 200.0))  # promedio 150
    estado = aplicar_transaccion(estado, _tx("AAPL", "VENTA", 5, 180.0))    # quedan 15 @150
    # MSFT independiente
    estado = aplicar_transaccion(estado, _tx("MSFT", "COMPRA", 3, 300.0))

    tenencias = calcular_tenencias(estado)

    assert tenencias["AAPL"]["cantidad"] == 15
    assert tenencias["AAPL"]["precio_promedio"] == pytest.approx(150.0)
    assert tenencias["MSFT"]["cantidad"] == 3
    assert tenencias["MSFT"]["precio_promedio"] == pytest.approx(300.0)


# ---------------------------------------------------------------------------
# T6.5 — Autenticación
# ---------------------------------------------------------------------------

def test_registrar_usuario_nuevo_anade_entrada_con_hash() -> None:
    """El nuevo registro NO debe contener la contraseña en claro."""
    nuevo = registrar_usuario([], "lady", "mi-clave-segura")

    assert len(nuevo) == 1
    entry = nuevo[0]
    assert entry["usuario"] == "lady"
    assert "salt" in entry and len(entry["salt"]) >= 32
    assert "hash" in entry and len(entry["hash"]) == 64  # sha256 hex
    # La contraseña en claro NUNCA debe aparecer en los datos persistidos.
    assert "mi-clave-segura" not in str(entry)


def test_registrar_usuario_duplicado_lanza() -> None:
    base = registrar_usuario([], "lady", "clave")

    with pytest.raises(UsuarioYaExiste):
        registrar_usuario(base, "lady", "otra-clave")


def test_verificar_credenciales_correctas_devuelve_true() -> None:
    usuarios = registrar_usuario([], "lady", "clave-correcta")

    assert verificar_credenciales(usuarios, "lady", "clave-correcta") is True


def test_verificar_credenciales_incorrectas_devuelve_false() -> None:
    usuarios = registrar_usuario([], "lady", "clave-correcta")

    assert verificar_credenciales(usuarios, "lady", "clave-mala") is False
    assert verificar_credenciales(usuarios, "no-existe", "x") is False


def test_hash_password_diferente_salt_genera_hash_diferente() -> None:
    """Dos usuarios con la misma contraseña deben tener hashes distintos."""
    h1 = hash_password("clave", "salt-uno")
    h2 = hash_password("clave", "salt-dos")

    assert h1 != h2
    # Pero el mismo input debe ser determinístico.
    assert hash_password("clave", "salt-uno") == h1


def test_guardar_y_cargar_usuarios_es_idempotente(tmp_path) -> None:
    ruta = tmp_path / "usuarios.json"
    usuarios = registrar_usuario([], "lady", "clave")

    guardar_usuarios(ruta, usuarios)
    cargados = cargar_usuarios(ruta)

    assert cargados == usuarios
