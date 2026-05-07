"""QA integration tests: ejecuta el pipeline real con yfinance y reporta.

Diseñado para correr una sola vez como verificación end-to-end del prototipo.
NO se incluye en pytest (depende de la red) ni se sube al repo (gitignored).
"""
from __future__ import annotations

import json
import sys
import tempfile
import traceback
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

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
    estado_inicial_portafolio,
    generar_senal,
    guardar_portafolio,
    guardar_usuarios,
    hash_password,
    registrar_usuario,
    verificar_credenciales,
)

TICKERS = ["AAPL", "MSFT", "TSLA", "NVDA", "SPY"]
RESULTADOS: list[tuple[str, bool, str]] = []


def caso(nombre: str):
    """Decorador simple que reporta éxito/fallo de cada caso."""
    def deco(fn):
        try:
            fn()
            RESULTADOS.append((nombre, True, ""))
            print(f"  [PASS]{nombre}")
        except AssertionError as e:
            RESULTADOS.append((nombre, False, f"AssertionError: {e}"))
            print(f"  [FAIL]{nombre} -- {e}")
        except Exception as e:
            RESULTADOS.append((nombre, False, f"{type(e).__name__}: {e}"))
            print(f"  [FAIL]{nombre} -- {type(e).__name__}: {e}")
            traceback.print_exc()
        return fn
    return deco


# ===========================================================================
# QA-2: Pipeline real con yfinance
# ===========================================================================
print("\n[QA-2] Pipeline end-to-end con yfinance")
print("-" * 60)

end = date.today()
start = end - timedelta(days=730)


def aplanar(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


for ticker in TICKERS:
    @caso(f"{ticker}: yfinance descarga > 100 filas")
    def _():
        df = aplanar(yf.download(ticker, start=start, end=end, progress=False, auto_adjust=False))
        assert not df.empty, "DataFrame vacío"
        assert len(df) > 100, f"Solo {len(df)} filas, esperaba > 100"

    @caso(f"{ticker}: SMA20/SMA50/RSI calculan sin NaN al final")
    def _():
        df = aplanar(yf.download(ticker, start=start, end=end, progress=False, auto_adjust=False))
        df = calcular_smas(df, ventanas=(20, 50))
        df["RSI_14"] = calcular_rsi(df["Close"], periodo=14)
        ult = df.iloc[-1]
        assert not pd.isna(ult["SMA_20"]), "SMA_20 NaN al final"
        assert not pd.isna(ult["SMA_50"]), "SMA_50 NaN al final"
        assert not pd.isna(ult["RSI_14"]), "RSI_14 NaN al final"
        assert 0 <= ult["RSI_14"] <= 100, f"RSI fuera de rango: {ult['RSI_14']}"

    @caso(f"{ticker}: señal es uno de COMPRAR/VENDER/MANTENER")
    def _():
        df = aplanar(yf.download(ticker, start=start, end=end, progress=False, auto_adjust=False))
        df = calcular_smas(df, ventanas=(20, 50))
        df["RSI_14"] = calcular_rsi(df["Close"], periodo=14)
        senal, motivo = generar_senal(df)
        assert senal in {"COMPRAR", "VENDER", "MANTENER"}, f"Señal desconocida: {senal}"
        assert motivo, "Motivo vacío"

    @caso(f"{ticker}: métricas con tipos correctos")
    def _():
        df = aplanar(yf.download(ticker, start=start, end=end, progress=False, auto_adjust=False))
        m = calcular_metricas(df)
        for k in ["precio_actual", "variacion_pct", "volatilidad_anual_pct", "stop_loss", "take_profit"]:
            assert k in m, f"Falta clave {k}"
            assert isinstance(m[k], (int, float)), f"{k} no es numérico: {type(m[k])}"
        # Sanity: stop-loss < precio < take-profit
        assert m["stop_loss"] < m["precio_actual"] < m["take_profit"]


# ===========================================================================
# QA-3: Edge cases
# ===========================================================================
print("\n[QA-3] Edge cases")
print("-" * 60)


@caso("yfinance con símbolo inválido devuelve DataFrame vacío")
def _():
    df = aplanar(yf.download("XXXNOEXISTE9999", start=start, end=end, progress=False, auto_adjust=False))
    assert df.empty, f"Esperaba empty, got {len(df)} filas"


@caso("Compra que excede saldo lanza TransaccionInvalida")
def _():
    estado = {"saldo_usd": 100.0, "transacciones": []}
    try:
        aplicar_transaccion(estado, {
            "fecha": "2026-05-07", "simbolo": "AAPL", "tipo": "COMPRA",
            "cantidad": 10, "precio_unitario": 50.0,
        })
        raise AssertionError("Debió lanzar")
    except TransaccionInvalida:
        pass


@caso("Venta sin tenencia lanza TransaccionInvalida")
def _():
    estado = {"saldo_usd": 10000.0, "transacciones": []}
    try:
        aplicar_transaccion(estado, {
            "fecha": "2026-05-07", "simbolo": "AAPL", "tipo": "VENTA",
            "cantidad": 1, "precio_unitario": 100.0,
        })
        raise AssertionError("Debió lanzar")
    except TransaccionInvalida:
        pass


@caso("Login con credenciales mal devuelve False")
def _():
    usuarios = registrar_usuario([], "user1", "pass-correcta-123")
    assert verificar_credenciales(usuarios, "user1", "otra-clave") is False
    assert verificar_credenciales(usuarios, "no-existe", "x") is False


@caso("Registrar usuario duplicado lanza UsuarioYaExiste")
def _():
    usuarios = registrar_usuario([], "user1", "clave")
    try:
        registrar_usuario(usuarios, "user1", "otra")
        raise AssertionError("Debió lanzar")
    except UsuarioYaExiste:
        pass


@caso("Hash determinístico con mismo input")
def _():
    h1 = hash_password("clave", "salt-fijo")
    h2 = hash_password("clave", "salt-fijo")
    assert h1 == h2
    h3 = hash_password("clave", "otro-salt")
    assert h1 != h3


@caso("JSON corrupto devuelve... lanza JSONDecodeError (esperado)")
def _():
    with tempfile.TemporaryDirectory() as d:
        ruta = Path(d) / "p.json"
        ruta.write_text("esto no es json válido", encoding="utf-8")
        try:
            cargar_portafolio(ruta)
            raise AssertionError("Debió lanzar JSONDecodeError")
        except json.JSONDecodeError:
            pass


@caso("Escritura atómica: tmp se renombra al destino")
def _():
    with tempfile.TemporaryDirectory() as d:
        ruta = Path(d) / "p.json"
        guardar_portafolio(ruta, {"saldo_usd": 1234.0, "transacciones": []})
        assert ruta.exists(), "El destino debe existir"
        # Tras un guardar exitoso no debe quedar el .tmp colgado.
        assert not (ruta.with_suffix(".json.tmp")).exists(), "tmp quedó colgado"
        recargado = cargar_portafolio(ruta)
        assert recargado["saldo_usd"] == 1234.0


@caso("Calcular tenencias con varias compras+ventas mantiene precio promedio")
def _():
    estado = {"saldo_usd": 100000.0, "transacciones": []}
    estado = aplicar_transaccion(estado, {
        "fecha": "2026-01-01", "simbolo": "AAPL", "tipo": "COMPRA",
        "cantidad": 10, "precio_unitario": 100.0,
    })
    estado = aplicar_transaccion(estado, {
        "fecha": "2026-02-01", "simbolo": "AAPL", "tipo": "COMPRA",
        "cantidad": 10, "precio_unitario": 200.0,
    })
    # Promedio ponderado = 150.
    estado = aplicar_transaccion(estado, {
        "fecha": "2026-03-01", "simbolo": "AAPL", "tipo": "VENTA",
        "cantidad": 5, "precio_unitario": 180.0,
    })
    ten = calcular_tenencias(estado)
    assert ten["AAPL"]["cantidad"] == 15
    assert abs(ten["AAPL"]["precio_promedio"] - 150.0) < 0.01


@caso("Deshacer última: replay sin la última tx restaura estado")
def _():
    s0 = estado_inicial_portafolio()
    s1 = aplicar_transaccion(s0, {
        "fecha": "2026-05-07", "simbolo": "AAPL", "tipo": "COMPRA",
        "cantidad": 5, "precio_unitario": 100.0,
    })
    s2 = aplicar_transaccion(s1, {
        "fecha": "2026-05-07", "simbolo": "MSFT", "tipo": "COMPRA",
        "cantidad": 2, "precio_unitario": 300.0,
    })
    # Replay sin la última.
    rebuild = estado_inicial_portafolio()
    for tx in s2["transacciones"][:-1]:
        rebuild = aplicar_transaccion(rebuild, tx)
    assert rebuild["saldo_usd"] == s1["saldo_usd"]
    assert len(rebuild["transacciones"]) == 1


# ===========================================================================
# QA-4: Aislamiento multi-usuario
# ===========================================================================
print("\n[QA-4] Aislamiento multi-usuario")
print("-" * 60)


@caso("Cada usuario tiene su propio archivo de portafolio")
def _():
    with tempfile.TemporaryDirectory() as d:
        ruta_a = Path(d) / "portafolio_alice.json"
        ruta_b = Path(d) / "portafolio_bob.json"

        estado_a = aplicar_transaccion(estado_inicial_portafolio(), {
            "fecha": "2026-05-07", "simbolo": "AAPL", "tipo": "COMPRA",
            "cantidad": 10, "precio_unitario": 187.45,
        })
        estado_b = aplicar_transaccion(estado_inicial_portafolio(), {
            "fecha": "2026-05-07", "simbolo": "TSLA", "tipo": "COMPRA",
            "cantidad": 3, "precio_unitario": 400.0,
        })

        guardar_portafolio(ruta_a, estado_a)
        guardar_portafolio(ruta_b, estado_b)

        a = cargar_portafolio(ruta_a)
        b = cargar_portafolio(ruta_b)

        assert a != b, "Los portafolios no deben ser iguales"
        assert "AAPL" in calcular_tenencias(a)
        assert "TSLA" in calcular_tenencias(b)
        assert "AAPL" not in calcular_tenencias(b), "Bob no debe ver tenencia de Alice"


@caso("Dos usuarios distintos en usuarios.json con login independiente")
def _():
    with tempfile.TemporaryDirectory() as d:
        ruta = Path(d) / "usuarios.json"
        usuarios = registrar_usuario([], "alice", "clave-a")
        usuarios = registrar_usuario(usuarios, "bob", "clave-b")
        guardar_usuarios(ruta, usuarios)

        cargados = cargar_usuarios(ruta)
        assert verificar_credenciales(cargados, "alice", "clave-a") is True
        assert verificar_credenciales(cargados, "bob", "clave-b") is True
        # Cruce de credenciales debe fallar.
        assert verificar_credenciales(cargados, "alice", "clave-b") is False
        assert verificar_credenciales(cargados, "bob", "clave-a") is False


# ===========================================================================
# Reporte
# ===========================================================================
print("\n" + "=" * 60)
total = len(RESULTADOS)
ok = sum(1 for _, p, _ in RESULTADOS if p)
ko = total - ok
print(f"Resultado: {ok}/{total} casos pasaron, {ko} fallaron")
print("=" * 60)
if ko > 0:
    print("\nFallos detallados:")
    for nombre, paso, err in RESULTADOS:
        if not paso:
            print(f"  [FAIL]{nombre}")
            print(f"     {err}")
    sys.exit(1)
else:
    print("ALL TESTS PASSED")
