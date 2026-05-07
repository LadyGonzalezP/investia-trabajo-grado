"""Sistema de apoyo a la toma de decisiones en inversión bursátil.

Prototipo académico (TRL5) — trabajo de grado.

Aplicación Streamlit de una sola capa:
* Autenticación local (sha256 + salt) con persistencia en ``usuarios.json``.
* Análisis técnico de un símbolo bursátil con datos reales de yfinance.
* Indicadores SMA20, SMA50 y RSI14, señales educativas, métricas y gráficas.
* Portafolio personal por usuario con saldo USD, registro de compras/ventas
  y persistencia en ``portafolio_<usuario>.json``.

NO ejecuta operaciones reales; NO es asesoría financiera.
"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
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
    generar_senal,
    guardar_portafolio,
    guardar_usuarios,
    registrar_usuario,
    verificar_credenciales,
)

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

RUTA_USUARIOS = Path("usuarios.json")
TICKERS_PRESET = ["AAPL", "MSFT", "TSLA", "NVDA", "SPY"]

DISCLAIMER = (
    "⚠️ Prototipo académico (TRL5). Las señales y métricas mostradas son "
    "educativas. **No constituyen asesoría financiera real** y este sistema "
    "no ejecuta operaciones bursátiles reales."
)


def ruta_portafolio_usuario(usuario: str) -> Path:
    """Cada usuario logueado tiene su propio archivo de portafolio."""
    return Path(f"portafolio_{usuario}.json")


# ---------------------------------------------------------------------------
# Datos de mercado (yfinance) — cacheado para no redescargar en cada interacción
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600, show_spinner="Descargando datos del mercado…")
def descargar_datos(simbolo: str, inicio: date, fin: date) -> pd.DataFrame:
    """Descarga el OHLCV diario para ``simbolo`` entre ``inicio`` y ``fin``.

    Si yfinance no encuentra el ticker o el rango está fuera de mercado,
    devuelve un DataFrame vacío. La capa UI muestra un error claro en ese caso.
    """
    df = yf.download(simbolo, start=inicio, end=fin, progress=False, auto_adjust=False)
    if df.empty:
        return df
    # Cuando yfinance recibe un solo ticker pero devuelve MultiIndex, lo aplanamos
    # para poder acceder simplemente a df["Close"].
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


@st.cache_data(ttl=300, show_spinner=False)
def precio_actual_simbolo(simbolo: str) -> float | None:
    """Precio de cierre más reciente para valorar tenencias del portafolio."""
    df = yf.download(simbolo, period="5d", progress=False, auto_adjust=False)
    if df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return float(df["Close"].iloc[-1])


# ---------------------------------------------------------------------------
# Gráficas Plotly
# ---------------------------------------------------------------------------

def grafica_precio_smas(df: pd.DataFrame, simbolo: str) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df["Close"], name="Cierre", line=dict(color="#1f77b4")))
    fig.add_trace(go.Scatter(x=df.index, y=df["SMA_20"], name="SMA 20", line=dict(color="#ff7f0e")))
    fig.add_trace(go.Scatter(x=df.index, y=df["SMA_50"], name="SMA 50", line=dict(color="#2ca02c")))
    fig.update_layout(
        title=f"{simbolo}: precio de cierre y medias móviles",
        xaxis_title="Fecha",
        yaxis_title="Precio (USD)",
        hovermode="x unified",
        height=420,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def grafica_rsi(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df["RSI_14"], name="RSI 14", line=dict(color="#9467bd")))
    fig.add_hline(y=70, line_dash="dash", line_color="red",
                  annotation_text="Sobrecompra (70)", annotation_position="right")
    fig.add_hline(y=30, line_dash="dash", line_color="green",
                  annotation_text="Sobreventa (30)", annotation_position="right")
    fig.update_layout(
        title="Índice de Fuerza Relativa (RSI 14)",
        xaxis_title="Fecha",
        yaxis_title="RSI",
        hovermode="x unified",
        height=300,
        yaxis=dict(range=[0, 100]),
    )
    return fig


# ---------------------------------------------------------------------------
# Pantalla de autenticación
# ---------------------------------------------------------------------------

def pagina_autenticacion() -> None:
    """Muestra tabs de Iniciar sesión / Crear cuenta. No accede a nada protegido."""
    st.title("📈 Sistema de apoyo a la toma de decisiones bursátiles")
    st.caption(DISCLAIMER)
    st.divider()

    tab_login, tab_registro = st.tabs(["🔑 Iniciar sesión", "✨ Crear cuenta"])

    with tab_login:
        with st.form("form_login", clear_on_submit=False):
            usuario = st.text_input("Usuario").strip()
            password = st.text_input("Contraseña", type="password")
            enviar = st.form_submit_button("Entrar", type="primary")
        if enviar:
            usuarios = cargar_usuarios(RUTA_USUARIOS)
            if verificar_credenciales(usuarios, usuario, password):
                st.session_state["usuario"] = usuario
                st.rerun()
            else:
                # Mensaje genérico a propósito: no revelar si falló el usuario o la clave.
                st.error("Usuario o contraseña incorrectos.")

    with tab_registro:
        with st.form("form_registro", clear_on_submit=False):
            nombre = st.text_input("Nombre de usuario (3–20 caracteres alfanuméricos)").strip()
            clave = st.text_input("Contraseña (mínimo 6 caracteres)", type="password")
            clave2 = st.text_input("Confirmar contraseña", type="password")
            enviar = st.form_submit_button("Crear cuenta", type="primary")
        if enviar:
            if not (3 <= len(nombre) <= 20) or not nombre.isalnum():
                st.error("El nombre debe ser alfanumérico y tener entre 3 y 20 caracteres.")
            elif len(clave) < 6:
                st.error("La contraseña debe tener al menos 6 caracteres.")
            elif clave != clave2:
                st.error("Las contraseñas no coinciden.")
            else:
                try:
                    usuarios = cargar_usuarios(RUTA_USUARIOS)
                    nuevos = registrar_usuario(usuarios, nombre, clave)
                    guardar_usuarios(RUTA_USUARIOS, nuevos)
                    st.success(
                        f"Cuenta '{nombre}' creada. Cambia a la pestaña "
                        f"'Iniciar sesión' para entrar."
                    )
                except UsuarioYaExiste as exc:
                    st.error(str(exc))


# ---------------------------------------------------------------------------
# Sección Análisis
# ---------------------------------------------------------------------------

def seccion_analisis() -> None:
    st.subheader("📊 Análisis técnico")

    cols = st.columns([2, 2, 2, 2])
    simbolo = cols[0].text_input("Símbolo bursátil", value="AAPL").upper().strip()
    preset = cols[1].selectbox("O elige un preset", options=["—"] + TICKERS_PRESET, index=0)
    if preset != "—":
        simbolo = preset

    hoy = date.today()
    fecha_inicio = cols[2].date_input(
        "Fecha de inicio", value=hoy - timedelta(days=730), max_value=hoy
    )
    fecha_fin = cols[3].date_input("Fecha de fin", value=hoy, max_value=hoy)

    if fecha_inicio >= fecha_fin:
        st.error("La fecha de inicio debe ser anterior a la fecha de fin.")
        return

    df = descargar_datos(simbolo, fecha_inicio, fecha_fin)
    if df.empty:
        st.error(
            f"No se encontraron datos para '{simbolo}' en el rango indicado. "
            f"Verifica que el símbolo exista en Yahoo Finance."
        )
        return

    if len(df) < 50:
        st.warning(
            "El rango es muy corto: la SMA de 50 días aún no es significativa. "
            "Considera ampliar el rango para una señal más confiable."
        )

    # Cálculo de indicadores y derivados
    df = calcular_smas(df, ventanas=(20, 50))
    df["RSI_14"] = calcular_rsi(df["Close"], periodo=14)
    metricas = calcular_metricas(df)

    # KPIs principales (5 columnas, según spec)
    k = st.columns(5)
    k[0].metric("Precio actual", f"${metricas['precio_actual']:.2f}")
    k[1].metric("Variación periodo", f"{metricas['variacion_pct']:+.2f}%")
    k[2].metric("Volatilidad anual", f"{metricas['volatilidad_anual_pct']:.2f}%")
    k[3].metric("Stop-loss (-5%)", f"${metricas['stop_loss']:.2f}")
    k[4].metric("Take-profit (+10%)", f"${metricas['take_profit']:.2f}")

    # Señal educativa: el color refuerza visualmente la decisión sugerida.
    try:
        senal, motivo = generar_senal(df)
        if senal == "COMPRAR":
            st.success(f"📈 Señal: **{senal}** — {motivo}")
        elif senal == "VENDER":
            st.error(f"📉 Señal: **{senal}** — {motivo}")
        else:
            st.warning(f"⏸️ Señal: **{senal}** — {motivo}")
        st.caption("_Señal educativa, no es asesoría financiera real._")
    except (IndexError, KeyError):
        st.warning("No hay suficientes datos para generar una señal.")

    # Gráficas Plotly interactivas
    st.plotly_chart(grafica_precio_smas(df, simbolo), use_container_width=True)
    st.plotly_chart(grafica_rsi(df), use_container_width=True)

    # Tabla de los últimos 30 días (suficiente para inspección visual sin saturar)
    st.subheader("Últimos 30 días")
    columnas_visibles = [c for c in
                         ["Open", "High", "Low", "Close", "Volume", "SMA_20", "SMA_50", "RSI_14"]
                         if c in df.columns]
    st.dataframe(df[columnas_visibles].tail(30).round(2), use_container_width=True)


# ---------------------------------------------------------------------------
# Sección Mi portafolio
# ---------------------------------------------------------------------------

def seccion_portafolio() -> None:
    usuario = st.session_state["usuario"]
    ruta = ruta_portafolio_usuario(usuario)
    estado = cargar_portafolio(ruta)
    tenencias = calcular_tenencias(estado)

    # Valoración a precio de mercado de cada tenencia
    filas_tenencias: list[dict] = []
    valor_tenencias = 0.0
    for sim, t in tenencias.items():
        precio = precio_actual_simbolo(sim)
        if precio is None:
            # Si yfinance falla, usamos el precio promedio como fallback explícito
            precio = t["precio_promedio"]
        valor_mercado = t["cantidad"] * precio
        valor_tenencias += valor_mercado
        pnl_abs = valor_mercado - t["costo_total"]
        pnl_pct = (pnl_abs / t["costo_total"]) * 100 if t["costo_total"] else 0.0
        filas_tenencias.append({
            "Símbolo": sim,
            "Cantidad": t["cantidad"],
            "Precio promedio (USD)": round(t["precio_promedio"], 2),
            "Precio actual (USD)": round(precio, 2),
            "Valor de mercado (USD)": round(valor_mercado, 2),
            "P&L (USD)": round(pnl_abs, 2),
            "P&L (%)": round(pnl_pct, 2),
        })

    saldo = estado["saldo_usd"]
    valor_total = saldo + valor_tenencias
    pnl_total = valor_total - SALDO_INICIAL_USD
    pnl_total_pct = (pnl_total / SALDO_INICIAL_USD) * 100

    # KPIs del portafolio
    k = st.columns(4)
    k[0].metric("Saldo en efectivo", f"${saldo:,.2f}")
    k[1].metric("Valor de tenencias", f"${valor_tenencias:,.2f}")
    k[2].metric("Valor total", f"${valor_total:,.2f}")
    k[3].metric(
        "P&L total",
        f"${pnl_total:+,.2f}",
        delta=f"{pnl_total_pct:+.2f}%",
    )

    st.divider()
    st.subheader("Registrar transacción")

    with st.form("form_tx", clear_on_submit=True):
        cols = st.columns([2, 2, 2, 2, 2])
        sim_in = cols[0].text_input("Símbolo", value="AAPL").upper().strip()
        tipo_in = cols[1].selectbox("Tipo", ["COMPRA", "VENTA"])
        cantidad_in = cols[2].number_input("Cantidad", min_value=1, step=1, value=1)
        precio_in = cols[3].number_input(
            "Precio unitario (USD)", min_value=0.01, step=0.01, value=100.00, format="%.2f"
        )
        fecha_in = cols[4].date_input("Fecha", value=date.today(), max_value=date.today())
        enviar = st.form_submit_button("Registrar transacción", type="primary")

    if enviar:
        tx = {
            "fecha": fecha_in.isoformat(),
            "simbolo": sim_in,
            "tipo": tipo_in,
            "cantidad": int(cantidad_in),
            "precio_unitario": float(precio_in),
        }
        try:
            nuevo_estado = aplicar_transaccion(estado, tx)
            guardar_portafolio(ruta, nuevo_estado)
            st.success(
                f"Transacción {tipo_in} de {cantidad_in} {sim_in} a "
                f"${precio_in:.2f} registrada."
            )
            st.rerun()
        except TransaccionInvalida as exc:
            st.error(str(exc))

    st.divider()

    # Tabla de tenencias actuales
    st.subheader("Tenencias actuales")
    if filas_tenencias:
        st.dataframe(pd.DataFrame(filas_tenencias), use_container_width=True, hide_index=True)
    else:
        st.info("Aún no tienes posiciones. Registra una compra para empezar.")

    # Histórico de transacciones + deshacer
    st.subheader("Histórico de transacciones")
    if estado["transacciones"]:
        df_tx = pd.DataFrame(estado["transacciones"])
        st.dataframe(df_tx, use_container_width=True, hide_index=True)

        if st.button("↩️ Deshacer última transacción"):
            # Recomponemos desde cero a partir del histórico recortado: así el saldo
            # y las tenencias quedan exactamente como estaban antes de la última tx,
            # incluso si hubo un encadenamiento complejo de compras/ventas.
            historico_recortado = estado["transacciones"][:-1]
            recompuesto = {"saldo_usd": SALDO_INICIAL_USD, "transacciones": []}
            for tx in historico_recortado:
                recompuesto = aplicar_transaccion(recompuesto, tx)
            guardar_portafolio(ruta, recompuesto)
            st.rerun()
    else:
        st.info("Aún no hay transacciones registradas para este usuario.")


# ---------------------------------------------------------------------------
# Aplicación principal
# ---------------------------------------------------------------------------

def main() -> None:
    st.set_page_config(
        page_title="Sistema de apoyo bursátil",
        page_icon="📈",
        layout="wide",
    )

    # Si el usuario no ha iniciado sesión, mostramos solo la pantalla de auth.
    if "usuario" not in st.session_state:
        pagina_autenticacion()
        return

    # Sidebar: estado de sesión + cerrar sesión
    with st.sidebar:
        st.success(f"Sesión activa: **{st.session_state['usuario']}**")
        st.caption("Cada usuario solo ve y modifica su propio portafolio.")
        if st.button("Cerrar sesión", use_container_width=True):
            st.session_state.clear()
            st.rerun()
        st.divider()
        st.markdown("**Tickers de referencia:**\n\n" + ", ".join(TICKERS_PRESET))

    # Disclaimer permanente arriba
    st.info(DISCLAIMER)
    st.title("📈 Sistema de apoyo a la toma de decisiones bursátiles")

    tab_analisis, tab_portafolio = st.tabs(["📊 Análisis", "💼 Mi portafolio"])
    with tab_analisis:
        seccion_analisis()
    with tab_portafolio:
        seccion_portafolio()

    # Disclaimer permanente al pie
    st.divider()
    st.caption(DISCLAIMER)


if __name__ == "__main__":
    main()
