"""Tests de UI con streamlit.testing.v1.AppTest.

Cubren los flujos manuales M-1 a M-4 documentados en QA_REPORT.md sin
necesidad de un navegador real. El framework AppTest ejecuta el script de
Streamlit, captura todos los widgets y permite simular interacciones
(clicks, inputs) y consultar ``session_state``.

yfinance se mockea a través de la fixture ``mock_yfinance`` para evitar
dependencias de red y obtener resultados determinísticos.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from tests.conftest import APP_PATH


# Helpers ---------------------------------------------------------------------

def _boton(at: AppTest, etiqueta_parcial: str):
    """Devuelve el primer botón cuyo label contiene ``etiqueta_parcial``.

    Los botones de Streamlit se identifican por label; sólo usamos `key` cuando
    es necesario para evitar colisiones.
    """
    for b in at.button:
        if etiqueta_parcial.lower() in str(b.label).lower():
            return b
    raise AssertionError(
        f"No se encontró botón con label que contenga '{etiqueta_parcial}'. "
        f"Botones disponibles: {[b.label for b in at.button]}"
    )


def _crear_y_loguear(at: AppTest, usuario: str, password: str) -> AppTest:
    """Atajo que recorre Welcome → Sign up → Login para los tests que ya
    asumen un usuario activo. Devuelve el AppTest tras el login exitoso."""
    _boton(at, "Get started").click()
    at.run(timeout=30)
    _boton(at, "Sign up").click()
    at.run(timeout=30)
    # En sign up: usuario, contraseña, confirmar contraseña.
    at.text_input[0].set_value(usuario)
    at.text_input[1].set_value(password)
    at.text_input[2].set_value(password)
    _boton(at, "Crear cuenta").click()
    at.run(timeout=30)
    # Tras crear cuenta, queda en login con success.
    at.text_input[0].set_value(usuario)
    at.text_input[1].set_value(password)
    _boton(at, "Continue").click()
    at.run(timeout=30)
    assert "usuario" in at.session_state and at.session_state["usuario"] == usuario, (
        f"No quedó logueado. usuario={at.session_state.filtered_state if hasattr(at.session_state, 'filtered_state') else dict(at.session_state)}"
    )
    return at


# ============================================================================
# M-1: Welcome → Login → Home
# ============================================================================

def test_welcome_screen_renders_logo_y_get_started(isolated_cwd):
    at = AppTest.from_file(APP_PATH).run(timeout=30)
    assert not at.exception, f"Excepción al cargar: {[e.message for e in at.exception]}"
    contenido = " ".join(m.value for m in at.markdown)
    assert "InvestIA" in contenido
    assert "Invierte con más claridad" in contenido
    assert any("Get started" in str(b.label) for b in at.button)


def test_get_started_navega_a_login(isolated_cwd):
    at = AppTest.from_file(APP_PATH).run(timeout=30)
    _boton(at, "Get started").click()
    at.run(timeout=30)
    assert at.session_state["auth_screen"] == "login"
    contenido = " ".join(m.value for m in at.markdown)
    assert "Welcome back" in contenido


def test_signup_crea_usuario_en_disco(isolated_cwd):
    at = AppTest.from_file(APP_PATH).run(timeout=30)
    _boton(at, "Get started").click()
    at.run(timeout=30)
    _boton(at, "Sign up").click()
    at.run(timeout=30)

    at.text_input[0].set_value("alice")
    at.text_input[1].set_value("clave-segura-123")
    at.text_input[2].set_value("clave-segura-123")
    _boton(at, "Crear cuenta").click()
    at.run(timeout=30)

    archivo = isolated_cwd / "usuarios.json"
    assert archivo.exists(), "Debió crearse usuarios.json"
    datos = json.loads(archivo.read_text(encoding="utf-8"))
    assert datos[0]["usuario"] == "alice"
    assert "alice" not in str(datos[0]).lower() or datos[0]["hash"], (
        "El hash debe estar presente"
    )
    # La contraseña en claro NO puede aparecer en el archivo.
    assert "clave-segura-123" not in archivo.read_text(encoding="utf-8")


def test_login_credenciales_incorrectas_muestra_error(isolated_cwd):
    """Crear usuario primero, luego intentar login con clave mala."""
    at = AppTest.from_file(APP_PATH).run(timeout=30)
    _boton(at, "Get started").click()
    at.run(timeout=30)
    _boton(at, "Sign up").click()
    at.run(timeout=30)
    at.text_input[0].set_value("bob")
    at.text_input[1].set_value("clave-correcta")
    at.text_input[2].set_value("clave-correcta")
    _boton(at, "Crear cuenta").click()
    at.run(timeout=30)

    # Tras signup, el código vuelve a auth_screen=login automáticamente.
    at.text_input[0].set_value("bob")
    at.text_input[1].set_value("clave-MALA")
    _boton(at, "Continue").click()
    at.run(timeout=30)

    assert "usuario" not in at.session_state, "No debió loguearse"
    errores = [e.value for e in at.error]
    assert any("incorrect" in err.lower() for err in errores), (
        f"Esperaba error de credenciales, vi: {errores}"
    )


def test_login_correcto_muestra_home_con_saludo(isolated_cwd, mock_yfinance):
    at = AppTest.from_file(APP_PATH).run(timeout=30)
    at = _crear_y_loguear(at, "carla", "secreta-xyz")
    assert at.session_state["screen"] == "home"
    contenido = " ".join(m.value for m in at.markdown)
    assert "Hola, Carla" in contenido
    assert "Valor del portafolio" in contenido
    assert "Recomendaciones" in contenido


# ============================================================================
# M-2: Bottom nav 4 secciones
# ============================================================================

def test_bottom_nav_tiene_4_items_alineados_con_figma(isolated_cwd, mock_yfinance):
    at = AppTest.from_file(APP_PATH).run(timeout=30)
    at = _crear_y_loguear(at, "diana", "clave-diana-2026")

    labels_nav = [
        b.label for b in at.button
        if any(x in str(b.label) for x in ["Home", "Portfolio", "Learn", "Profile"])
    ]
    assert "🏠 Home" in labels_nav
    assert "💼 Portfolio" in labels_nav
    assert "📚 Learn" in labels_nav
    assert "👤 Profile" in labels_nav
    # Garantizamos que NO existe "Análisis" en la nav (pasa a sub-pantalla).
    assert not any("Análisis" in str(b.label) and "técnico" not in str(b.label)
                   for b in at.button)


def test_bottom_nav_navega_entre_secciones(isolated_cwd, mock_yfinance):
    at = AppTest.from_file(APP_PATH).run(timeout=30)
    at = _crear_y_loguear(at, "elena", "clave-elena-2026")
    assert at.session_state["screen"] == "home"

    _boton(at, "Portfolio").click()
    at.run(timeout=30)
    assert at.session_state["screen"] == "portfolio"

    _boton(at, "Learn").click()
    at.run(timeout=30)
    assert at.session_state["screen"] == "learn"

    _boton(at, "Profile").click()
    at.run(timeout=30)
    assert at.session_state["screen"] == "profile"

    _boton(at, "Home").click()
    at.run(timeout=30)
    assert at.session_state["screen"] == "home"


def test_pantalla_learn_explica_indicadores(isolated_cwd, mock_yfinance):
    at = AppTest.from_file(APP_PATH).run(timeout=30)
    at = _crear_y_loguear(at, "fede", "clave-fede-123")
    _boton(at, "Learn").click()
    at.run(timeout=30)

    contenido = " ".join(m.value for m in at.markdown)
    assert "SMA" in contenido
    assert "RSI" in contenido
    assert "Volatilidad" in contenido
    assert "Sobrecompra" in contenido or "sobrecompra" in contenido


# ============================================================================
# M-3: Drill-in del Home al Análisis técnico
# ============================================================================

def test_card_recomendacion_navega_a_analisis(isolated_cwd, mock_yfinance):
    at = AppTest.from_file(APP_PATH).run(timeout=30)
    at = _crear_y_loguear(at, "gina", "clave-gina-2026")
    assert at.session_state["screen"] == "home"

    _boton(at, "Ver análisis técnico de AAPL").click()
    at.run(timeout=30)

    assert at.session_state["screen"] == "analysis"
    assert at.session_state["simbolo_seleccionado"] == "AAPL"
    contenido = " ".join(m.value for m in at.markdown)
    assert "Análisis técnico" in contenido


def test_volver_al_home_desde_analisis_limpia_seleccion(isolated_cwd, mock_yfinance):
    at = AppTest.from_file(APP_PATH).run(timeout=30)
    at = _crear_y_loguear(at, "hugo", "clave-hugo-2026")
    _boton(at, "Ver análisis técnico de MSFT").click()
    at.run(timeout=30)

    _boton(at, "Volver al Home").click()
    at.run(timeout=30)
    assert at.session_state["screen"] == "home"
    assert "simbolo_seleccionado" not in at.session_state


# ============================================================================
# M-4: Compra en Portfolio → persistencia entre sesiones
# ============================================================================

def test_compra_descuenta_saldo_y_se_persiste(isolated_cwd, mock_yfinance):
    at = AppTest.from_file(APP_PATH).run(timeout=30)
    at = _crear_y_loguear(at, "irene", "clave-irene-2026")

    _boton(at, "Portfolio").click()
    at.run(timeout=30)

    # Estructura del formulario de transacción dentro de la pantalla:
    # text_input[0]=Símbolo, selectbox=Tipo, number_input[0]=Cantidad,
    # number_input[1]=Precio, date_input=Fecha.
    at.text_input[0].set_value("AAPL")
    at.selectbox[0].set_value("COMPRA")
    at.number_input[0].set_value(10)
    at.number_input[1].set_value(150.00)
    _boton(at, "Registrar").click()
    at.run(timeout=30)

    # Saldo: 10000 - (10*150) = 8500.
    archivo = isolated_cwd / "portafolio_irene.json"
    assert archivo.exists(), "Debió crearse el portafolio del usuario"
    estado = json.loads(archivo.read_text(encoding="utf-8"))
    assert estado["saldo_usd"] == pytest.approx(8500.0)
    assert len(estado["transacciones"]) == 1
    assert estado["transacciones"][0]["simbolo"] == "AAPL"
    assert estado["transacciones"][0]["cantidad"] == 10


def test_compra_que_excede_saldo_muestra_error(isolated_cwd, mock_yfinance):
    at = AppTest.from_file(APP_PATH).run(timeout=30)
    at = _crear_y_loguear(at, "jose", "clave-jose-2026")
    _boton(at, "Portfolio").click()
    at.run(timeout=30)

    # 100 unidades a 1000 = 100.000 > saldo inicial 10.000.
    at.text_input[0].set_value("AAPL")
    at.selectbox[0].set_value("COMPRA")
    at.number_input[0].set_value(100)
    at.number_input[1].set_value(1000.00)
    _boton(at, "Registrar").click()
    at.run(timeout=30)

    errores = [e.value for e in at.error]
    assert any("Saldo insuficiente" in err for err in errores), (
        f"Esperaba error de saldo, vi: {errores}"
    )

    # Verificar que NO se persistió la transacción inválida.
    archivo = isolated_cwd / "portafolio_jose.json"
    if archivo.exists():
        estado = json.loads(archivo.read_text(encoding="utf-8"))
        assert estado["transacciones"] == [], "No debió guardar la tx inválida"


def test_persistencia_entre_sesiones(isolated_cwd, mock_yfinance):
    """Comprar, cerrar sesión, volver a entrar → la transacción sigue ahí."""
    at = AppTest.from_file(APP_PATH).run(timeout=30)
    at = _crear_y_loguear(at, "kira", "clave-kira-2026")
    _boton(at, "Portfolio").click()
    at.run(timeout=30)
    at.text_input[0].set_value("MSFT")
    at.selectbox[0].set_value("COMPRA")
    at.number_input[0].set_value(2)
    at.number_input[1].set_value(400.00)
    _boton(at, "Registrar").click()
    at.run(timeout=30)

    # Cerrar sesión.
    _boton(at, "Profile").click()
    at.run(timeout=30)
    _boton(at, "Cerrar sesión").click()
    at.run(timeout=30)
    assert "usuario" not in at.session_state

    # Volver a entrar.
    _boton(at, "Get started").click()
    at.run(timeout=30)
    at.text_input[0].set_value("kira")
    at.text_input[1].set_value("clave-kira-2026")
    _boton(at, "Continue").click()
    at.run(timeout=30)

    # En el archivo del portafolio sigue la compra.
    estado = json.loads((isolated_cwd / "portafolio_kira.json").read_text(encoding="utf-8"))
    assert len(estado["transacciones"]) == 1
    assert estado["transacciones"][0]["simbolo"] == "MSFT"
    assert estado["transacciones"][0]["cantidad"] == 2


# ============================================================================
# Logout / aislamiento entre cuentas
# ============================================================================

def test_aislamiento_dos_usuarios_no_ven_el_portafolio_del_otro(
    isolated_cwd, mock_yfinance
):
    # Alice compra AAPL.
    at = AppTest.from_file(APP_PATH).run(timeout=30)
    at = _crear_y_loguear(at, "alice2", "alice-clave-2026")
    _boton(at, "Portfolio").click()
    at.run(timeout=30)
    at.text_input[0].set_value("AAPL")
    at.selectbox[0].set_value("COMPRA")
    at.number_input[0].set_value(5)
    at.number_input[1].set_value(180.00)
    _boton(at, "Registrar").click()
    at.run(timeout=30)
    _boton(at, "Profile").click()
    at.run(timeout=30)
    _boton(at, "Cerrar sesión").click()
    at.run(timeout=30)

    # Bob entra y compra TSLA.
    at = _crear_y_loguear(at, "bob2", "bob-clave-2026")
    _boton(at, "Portfolio").click()
    at.run(timeout=30)
    at.text_input[0].set_value("TSLA")
    at.selectbox[0].set_value("COMPRA")
    at.number_input[0].set_value(3)
    at.number_input[1].set_value(400.00)
    _boton(at, "Registrar").click()
    at.run(timeout=30)

    portafolio_alice = json.loads(
        (isolated_cwd / "portafolio_alice2.json").read_text(encoding="utf-8")
    )
    portafolio_bob = json.loads(
        (isolated_cwd / "portafolio_bob2.json").read_text(encoding="utf-8")
    )
    assert portafolio_alice["transacciones"][0]["simbolo"] == "AAPL"
    assert portafolio_bob["transacciones"][0]["simbolo"] == "TSLA"
    # No hay cruces.
    assert all(tx["simbolo"] != "TSLA" for tx in portafolio_alice["transacciones"])
    assert all(tx["simbolo"] != "AAPL" for tx in portafolio_bob["transacciones"])
