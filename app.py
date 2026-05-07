"""Sistema de apoyo a la toma de decisiones en inversión bursátil — InvestIA.

Prototipo académico (TRL5) — trabajo de grado.

Aplicación Streamlit de una sola capa, con diseño visual estilo aplicación
móvil basado en el prototipo de Figma "InvestIA Mobile App". Mantiene toda
la lógica de negocio en ``logica.py`` (testeada con pytest) y solo gestiona
UI, sesión y orquestación aquí.

Pantallas:
* Welcome → Login / Sign up (flujo de autenticación).
* Home (dashboard) → AI Recommendations por ticker preset.
* Análisis → análisis técnico detallado con SMAs, RSI, señales y métricas.
* Portfolio → tenencias del usuario, transacciones, P&L.
* Profile → datos del usuario y cierre de sesión.

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
# Constantes (paleta InvestIA y configuración)
# ---------------------------------------------------------------------------

RUTA_USUARIOS = Path("usuarios.json")

# Tickers presentados en el Home como "AI Recommendations".
TICKERS_PRESET = ["AAPL", "MSFT", "TSLA", "NVDA", "SPY"]

# Nombres "amigables" para mostrar bajo el ticker en las cards.
NOMBRES_TICKER = {
    "AAPL": "Apple Inc.",
    "MSFT": "Microsoft Corp.",
    "TSLA": "Tesla Inc.",
    "NVDA": "NVIDIA Corp.",
    "SPY": "S&P 500 ETF",
}

# Paleta InvestIA — alineada con la captura del Figma.
COLOR_PRIMARIO = "#2563EB"      # azul botones y header
COLOR_PRIMARIO_OSCURO = "#1D4ED8"
COLOR_FONDO = "#FFFFFF"
COLOR_FONDO_SUAVE = "#F8FAFC"
COLOR_TEXTO = "#0F172A"
COLOR_TEXTO_MUTED = "#64748B"
COLOR_VERDE = "#10B981"         # señal COMPRAR / variaciones positivas
COLOR_AZUL_INFO = "#3B82F6"     # señal MANTENER
COLOR_ROJO = "#EF4444"          # señal VENDER / variaciones negativas
COLOR_BORDE = "#E2E8F0"

DISCLAIMER = (
    "Prototipo académico (TRL5). Las señales y métricas mostradas son "
    "educativas. **No constituyen asesoría financiera real** y este sistema "
    "no ejecuta operaciones bursátiles reales."
)


def ruta_portafolio_usuario(usuario: str) -> Path:
    """Cada usuario tiene su archivo de portafolio aislado."""
    return Path(f"portafolio_{usuario}.json")


# ---------------------------------------------------------------------------
# CSS móvil — inyectado una sola vez por sesión
# ---------------------------------------------------------------------------

def inyectar_css() -> None:
    """Inyecta el CSS que adapta Streamlit al look mobile-first de InvestIA.

    Aplica: contenedor estrecho centrado (efecto móvil), cards con bordes
    redondeados y sombra suave, badges Buy/Hold/Sell, botones de marca y
    espaciado reducido. Mantenemos todo el styling en este bloque para que
    sea sencillo de auditar.
    """
    st.markdown(
        f"""
        <style>
        /* Contenedor principal en ancho fijo tipo móvil. */
        .main .block-container {{
            max-width: 460px;
            padding-top: 1rem;
            padding-bottom: 6rem;  /* espacio para la bottom-nav fija */
            padding-left: 1rem;
            padding-right: 1rem;
        }}

        /* Esconder la barra superior de Streamlit y la sidebar. */
        header[data-testid="stHeader"] {{ display: none; }}
        section[data-testid="stSidebar"] {{ display: none; }}

        /* Tipografía y colores base. */
        html, body, [class*="css"] {{
            color: {COLOR_TEXTO};
        }}
        h1, h2, h3 {{
            color: {COLOR_TEXTO};
            font-weight: 700;
        }}

        /* Cards genéricos (envueltos por nosotros con st.markdown). */
        .iv-card {{
            background: white;
            border: 1px solid {COLOR_BORDE};
            border-radius: 16px;
            padding: 1rem 1.1rem;
            box-shadow: 0 1px 2px rgba(15,23,42,0.04);
            margin-bottom: 0.9rem;
        }}

        /* Hero azul (Home). */
        .iv-hero {{
            background: {COLOR_PRIMARIO};
            color: white;
            border-radius: 0 0 24px 24px;
            padding: 1.5rem 1.2rem 2.2rem 1.2rem;
            margin: -1rem -1rem 1.5rem -1rem;
        }}
        .iv-hero h2 {{ color: white; margin: 0; font-size: 1.4rem; }}
        .iv-hero p {{ color: rgba(255,255,255,0.85); margin: 0.3rem 0 0 0; font-size: 0.9rem; }}

        /* Card del valor del portafolio que "flota" sobre el hero. */
        .iv-portfolio-card {{
            background: white;
            border-radius: 16px;
            padding: 1rem 1.2rem;
            box-shadow: 0 4px 12px rgba(15,23,42,0.08);
            margin-top: -2rem;
            margin-bottom: 1.5rem;
        }}
        .iv-portfolio-card .iv-label {{
            font-size: 0.95rem;
            color: {COLOR_TEXTO_MUTED};
        }}
        .iv-portfolio-card .iv-value {{
            font-size: 1.7rem;
            font-weight: 800;
            color: {COLOR_TEXTO};
            margin-top: 0.2rem;
        }}
        .iv-portfolio-card .iv-delta-pos {{ color: {COLOR_VERDE}; font-weight: 600; }}
        .iv-portfolio-card .iv-delta-neg {{ color: {COLOR_ROJO};  font-weight: 600; }}

        /* Badges de señal (Buy / Hold / Sell). */
        .iv-badge {{
            display: inline-block;
            padding: 2px 10px;
            border-radius: 999px;
            font-size: 0.78rem;
            font-weight: 600;
            color: white;
            margin-left: 6px;
            vertical-align: middle;
        }}
        .iv-badge-buy  {{ background: {COLOR_VERDE}; }}
        .iv-badge-hold {{ background: {COLOR_AZUL_INFO}; }}
        .iv-badge-sell {{ background: {COLOR_ROJO}; }}

        /* Botones primarios y secundarios redondeados. */
        .stButton > button {{
            border-radius: 12px;
            font-weight: 600;
            padding: 0.55rem 1rem;
        }}
        .stButton > button[kind="primary"] {{
            background: {COLOR_PRIMARIO};
            border: none;
        }}
        .stButton > button[kind="primary"]:hover {{
            background: {COLOR_PRIMARIO_OSCURO};
        }}

        /* Inputs con bordes finos InvestIA. */
        .stTextInput > div > div > input,
        .stNumberInput > div > div > input,
        .stDateInput > div > div > input {{
            border-radius: 10px;
            border: 1px solid {COLOR_BORDE};
        }}

        /* Tabs internos (Análisis / Portfolio detalle): aspecto píldora. */
        .stTabs [data-baseweb="tab-list"] {{
            gap: 4px;
        }}
        .stTabs [data-baseweb="tab"] {{
            background: {COLOR_FONDO_SUAVE};
            border-radius: 10px;
            padding: 0.4rem 0.9rem;
        }}
        .stTabs [aria-selected="true"] {{
            background: {COLOR_PRIMARIO} !important;
            color: white !important;
        }}

        /* Bottom navigation: contenedor de las 4 columnas con buttons. */
        .iv-bottom-nav {{
            position: fixed;
            bottom: 0;
            left: 50%;
            transform: translateX(-50%);
            width: 100%;
            max-width: 460px;
            background: white;
            border-top: 1px solid {COLOR_BORDE};
            padding: 0.4rem 0.4rem 0.6rem 0.4rem;
            z-index: 999;
            box-shadow: 0 -2px 12px rgba(15,23,42,0.06);
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Datos de mercado (cacheado)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600, show_spinner="Descargando datos del mercado…")
def descargar_datos(simbolo: str, inicio: date, fin: date) -> pd.DataFrame:
    """Descarga OHLCV diario para el rango pedido. DataFrame vacío si falla."""
    df = yf.download(simbolo, start=inicio, end=fin, progress=False, auto_adjust=False)
    if df.empty:
        return df
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


@st.cache_data(ttl=600, show_spinner=False)
def datos_recientes_simbolo(simbolo: str, dias: int = 90) -> pd.DataFrame:
    """Datos recientes para mostrar la mini-gráfica del Home."""
    fin = date.today()
    inicio = fin - timedelta(days=dias)
    return descargar_datos(simbolo, inicio, fin)


def precio_actual_simbolo(simbolo: str) -> float | None:
    """Último precio de cierre. None si no hay datos disponibles."""
    df = datos_recientes_simbolo(simbolo, dias=10)
    if df.empty:
        return None
    return float(df["Close"].iloc[-1])


# ---------------------------------------------------------------------------
# Componentes visuales reutilizables
# ---------------------------------------------------------------------------

CLASE_BADGE = {
    "COMPRAR": ("iv-badge-buy", "Buy"),
    "MANTENER": ("iv-badge-hold", "Hold"),
    "VENDER": ("iv-badge-sell", "Sell"),
}


def html_badge(senal: str) -> str:
    """Devuelve el HTML del badge según la señal interna (COMPRAR/MANTENER/VENDER)."""
    clase, etiqueta = CLASE_BADGE.get(senal, ("iv-badge-hold", senal))
    return f'<span class="iv-badge {clase}">{etiqueta}</span>'


def grafica_sparkline(df: pd.DataFrame) -> go.Figure:
    """Mini-barras del Close reciente, estilo del Figma. Sin ejes."""
    valores = df["Close"].tail(30)
    fig = go.Figure(go.Bar(
        x=list(range(len(valores))),
        y=valores.values,
        marker=dict(color=COLOR_PRIMARIO),
    ))
    fig.update_layout(
        height=70,
        margin=dict(l=0, r=0, t=0, b=0),
        showlegend=False,
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        plot_bgcolor=COLOR_FONDO_SUAVE,
        paper_bgcolor="white",
        bargap=0.4,
    )
    return fig


def grafica_precio_smas(df: pd.DataFrame, simbolo: str) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df["Close"], name="Cierre",
                             line=dict(color=COLOR_PRIMARIO, width=2)))
    fig.add_trace(go.Scatter(x=df.index, y=df["SMA_20"], name="SMA 20",
                             line=dict(color="#F59E0B", width=1.5)))
    fig.add_trace(go.Scatter(x=df.index, y=df["SMA_50"], name="SMA 50",
                             line=dict(color=COLOR_VERDE, width=1.5)))
    fig.update_layout(
        title=f"{simbolo} · precio y medias móviles",
        xaxis_title=None,
        yaxis_title="USD",
        hovermode="x unified",
        height=320,
        margin=dict(l=10, r=10, t=40, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def grafica_rsi(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df["RSI_14"], name="RSI 14",
                             line=dict(color="#9333EA", width=2)))
    fig.add_hline(y=70, line_dash="dash", line_color=COLOR_ROJO,
                  annotation_text="Sobrecompra", annotation_position="right")
    fig.add_hline(y=30, line_dash="dash", line_color=COLOR_VERDE,
                  annotation_text="Sobreventa", annotation_position="right")
    fig.update_layout(
        title="RSI 14",
        xaxis_title=None,
        yaxis_title=None,
        hovermode="x unified",
        height=240,
        margin=dict(l=10, r=10, t=40, b=10),
        yaxis=dict(range=[0, 100]),
    )
    return fig


# ---------------------------------------------------------------------------
# Pantallas de autenticación: Welcome / Login / Sign up
# ---------------------------------------------------------------------------

def pantalla_welcome() -> None:
    """Onboarding: logo, lema y botón 'Get started'."""
    st.markdown(
        f"""
        <div style="text-align:center; padding-top: 4rem;">
            <div style="
                display:inline-flex; align-items:center; justify-content:center;
                width:72px; height:72px; background:{COLOR_PRIMARIO};
                border-radius:18px; margin-bottom:1.2rem;
                box-shadow: 0 8px 20px rgba(37,99,235,0.25);
                font-size:32px; color:white;
            ">📈</div>
            <h1 style="margin:0 0 0.6rem 0;">InvestIA</h1>
            <h3 style="margin:0 0 1rem 0; color:{COLOR_TEXTO};">
                Invierte con más claridad y menos miedo
            </h3>
            <p style="color:{COLOR_TEXTO_MUTED}; max-width:340px; margin: 0 auto;">
                Tu asistente educativo de inversión que te ayuda a
                entender el mercado bursátil con confianza.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.write("")
    st.write("")
    if st.button("Get started", type="primary", use_container_width=True):
        st.session_state.auth_screen = "login"
        st.rerun()
    st.caption(DISCLAIMER)


def pantalla_login() -> None:
    if st.button("← Atrás", key="back_login"):
        st.session_state.auth_screen = "welcome"
        st.rerun()
    st.markdown("### Welcome back")
    st.caption("Inicia sesión para continuar tu camino de inversión")

    with st.form("form_login", clear_on_submit=False):
        usuario = st.text_input("👤  Usuario", placeholder="tu-usuario").strip()
        password = st.text_input("🔒  Contraseña", type="password", placeholder="••••••••")
        enviar = st.form_submit_button("Continue", type="primary", use_container_width=True)

    if enviar:
        usuarios = cargar_usuarios(RUTA_USUARIOS)
        if verificar_credenciales(usuarios, usuario, password):
            st.session_state["usuario"] = usuario
            st.session_state["screen"] = "home"
            # Limpiamos el flag de pantalla de auth para no quedarnos pegados.
            st.session_state.pop("auth_screen", None)
            st.rerun()
        else:
            # Mensaje deliberadamente genérico: no revelamos cuál de los dos falló.
            st.error("Usuario o contraseña incorrectos.")

    st.markdown(
        f"<p style='text-align:center; margin-top:1.5rem; color:{COLOR_TEXTO_MUTED};'>"
        "¿No tienes cuenta?</p>",
        unsafe_allow_html=True,
    )
    if st.button("Sign up", key="goto_signup", use_container_width=True):
        st.session_state.auth_screen = "signup"
        st.rerun()


def pantalla_signup() -> None:
    if st.button("← Atrás", key="back_signup"):
        st.session_state.auth_screen = "login"
        st.rerun()
    st.markdown("### Crear cuenta")
    st.caption("3–20 caracteres alfanuméricos · contraseña ≥ 6 caracteres")

    with st.form("form_signup", clear_on_submit=False):
        nombre = st.text_input("👤  Usuario").strip()
        clave = st.text_input("🔒  Contraseña", type="password")
        clave2 = st.text_input("🔒  Confirmar contraseña", type="password")
        enviar = st.form_submit_button("Crear cuenta", type="primary", use_container_width=True)

    if enviar:
        if not (3 <= len(nombre) <= 20) or not nombre.isalnum():
            st.error("El usuario debe ser alfanumérico y tener entre 3 y 20 caracteres.")
        elif len(clave) < 6:
            st.error("La contraseña debe tener al menos 6 caracteres.")
        elif clave != clave2:
            st.error("Las contraseñas no coinciden.")
        else:
            try:
                usuarios = cargar_usuarios(RUTA_USUARIOS)
                nuevos = registrar_usuario(usuarios, nombre, clave)
                guardar_usuarios(RUTA_USUARIOS, nuevos)
                st.success(f"Cuenta '{nombre}' creada. Vuelve a Iniciar sesión.")
                st.session_state.auth_screen = "login"
            except UsuarioYaExiste as exc:
                st.error(str(exc))


def pagina_autenticacion() -> None:
    """Router de pantallas de autenticación según ``st.session_state.auth_screen``."""
    auth_screen = st.session_state.get("auth_screen", "welcome")
    if auth_screen == "welcome":
        pantalla_welcome()
    elif auth_screen == "login":
        pantalla_login()
    elif auth_screen == "signup":
        pantalla_signup()


# ---------------------------------------------------------------------------
# Pantalla Home (dashboard con AI Recommendations)
# ---------------------------------------------------------------------------

def _calcular_recomendacion(simbolo: str) -> dict | None:
    """Calcula la recomendación de un ticker para mostrar en el Home.

    Devuelve un dict con precio, variación reciente, señal y DataFrame para
    la sparkline. Si yfinance no devuelve datos o algo falla en el cálculo,
    devuelve ``None`` (la home muestra un placeholder en su lugar).
    """
    try:
        df = datos_recientes_simbolo(simbolo, dias=120)
        if df.empty or len(df) < 50:
            return None
        df = calcular_smas(df, ventanas=(20, 50))
        df["RSI_14"] = calcular_rsi(df["Close"], periodo=14)
        senal, _motivo = generar_senal(df)

        precio_actual = float(df["Close"].iloc[-1])
        precio_previo = float(df["Close"].iloc[-2])
        variacion_pct = (precio_actual / precio_previo - 1) * 100

        return {
            "simbolo": simbolo,
            "nombre": NOMBRES_TICKER.get(simbolo, simbolo),
            "precio": precio_actual,
            "variacion": variacion_pct,
            "senal": senal,
            "df": df,
        }
    except Exception:
        # yfinance puede lanzar errores transitorios; nunca queremos que el
        # Home muera por uno de los 5 tickers.
        return None


def pantalla_home() -> None:
    usuario = st.session_state["usuario"]
    estado = cargar_portafolio(ruta_portafolio_usuario(usuario))

    # Hero azul con saludo personalizado.
    st.markdown(
        f"""
        <div class="iv-hero">
            <h2>Hola, {usuario.capitalize()}</h2>
            <p>Aquí están tus recomendaciones personalizadas</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Card flotante con el valor del portafolio.
    tenencias = calcular_tenencias(estado)
    valor_tenencias = 0.0
    for sim, t in tenencias.items():
        precio = precio_actual_simbolo(sim) or t["precio_promedio"]
        valor_tenencias += t["cantidad"] * precio
    valor_total = estado["saldo_usd"] + valor_tenencias
    delta_total = valor_total - SALDO_INICIAL_USD
    delta_pct = (delta_total / SALDO_INICIAL_USD) * 100
    clase_delta = "iv-delta-pos" if delta_total >= 0 else "iv-delta-neg"
    flecha = "↗" if delta_total >= 0 else "↘"

    st.markdown(
        f"""
        <div class="iv-portfolio-card">
            <div class="iv-label">Valor del portafolio</div>
            <div class="iv-value">${valor_total:,.2f}</div>
            <div class="{clase_delta}">{flecha} {delta_total:+,.2f} ({delta_pct:+.2f}%) vs. inicial</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("### Recomendaciones")

    # Pre-calcular para saber si TODAS fallaron (caso degradado típico cuando
    # yfinance está temporalmente abajo o la red bloquea Yahoo Finance).
    with st.spinner("Calculando recomendaciones…"):
        recs = [(simbolo, _calcular_recomendacion(simbolo)) for simbolo in TICKERS_PRESET]

    if all(rec is None for _, rec in recs):
        st.warning(
            "No se pudieron cargar datos de mercado en este momento. "
            "Yahoo Finance puede estar lento o bloqueado. Intenta de nuevo en "
            "un par de minutos o revisa tu conexión."
        )
        return

    # Una card por ticker preset con la señal calculada en vivo. La card es
    # un bloque visual (HTML), y debajo va un botón ancho que navega a
    # Análisis técnico para ese símbolo. Streamlit no permite hacer
    # `onClick` en HTML arbitrario sin componentes externos, así que el
    # botón es la forma idiomática de navegar.
    for simbolo, rec in recs:
        if rec is None:
            st.markdown(
                f"<div class='iv-card'><b>{simbolo}</b> · sin datos disponibles</div>",
                unsafe_allow_html=True,
            )
            continue

        color_var = COLOR_VERDE if rec["variacion"] >= 0 else COLOR_ROJO
        st.markdown(
            f"""
            <div class="iv-card" style="margin-bottom:0;">
                <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                    <div>
                        <div style="font-weight:700; font-size:1.05rem;">
                            {rec['simbolo']} {html_badge(rec['senal'])}
                        </div>
                        <div style="color:{COLOR_TEXTO_MUTED}; font-size:0.85rem;">
                            {rec['nombre']}
                        </div>
                    </div>
                    <div style="text-align:right;">
                        <div style="font-weight:700;">${rec['precio']:.2f}</div>
                        <div style="color:{color_var}; font-size:0.85rem;">
                            {rec['variacion']:+.2f}%
                        </div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.plotly_chart(grafica_sparkline(rec["df"]), use_container_width=True,
                        config={"displayModeBar": False})
        if st.button(f"Ver análisis técnico de {simbolo} →",
                     key=f"detail_{simbolo}", use_container_width=True):
            st.session_state.simbolo_seleccionado = simbolo
            st.session_state.screen = "analysis"
            st.rerun()


# ---------------------------------------------------------------------------
# Pantalla Análisis (técnico detallado)
# ---------------------------------------------------------------------------

def pantalla_analisis() -> None:
    # Si venimos desde el Home tocando una recomendación, vuelve a la home
    # con un botón claro. Mejor UX que "perderse" en una sub-pantalla.
    if st.session_state.get("simbolo_seleccionado"):
        if st.button("← Volver al Home", key="back_home_from_analysis"):
            st.session_state.pop("simbolo_seleccionado", None)
            st.session_state.screen = "home"
            st.rerun()

    st.markdown("### 📊 Análisis técnico")

    # Si el usuario llegó tocando una recomendación, pre-seleccionamos su ticker.
    seleccionado = st.session_state.get("simbolo_seleccionado", TICKERS_PRESET[0])
    if seleccionado not in TICKERS_PRESET:
        TICKERS_PRESET.append(seleccionado)
    simbolo = st.selectbox(
        "Símbolo bursátil",
        options=TICKERS_PRESET + ["Otro…"],
        index=TICKERS_PRESET.index(seleccionado),
    )
    if simbolo == "Otro…":
        simbolo = st.text_input("Escribe el símbolo", value="AAPL").upper().strip()

    hoy = date.today()
    cols = st.columns(2)
    fecha_inicio = cols[0].date_input("Inicio", value=hoy - timedelta(days=730), max_value=hoy)
    fecha_fin = cols[1].date_input("Fin", value=hoy, max_value=hoy)

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
            "Rango muy corto: la SMA50 aún no es significativa. Considera ampliar."
        )

    df = calcular_smas(df, ventanas=(20, 50))
    df["RSI_14"] = calcular_rsi(df["Close"], periodo=14)
    metricas = calcular_metricas(df)

    # KPIs apilados en cards (2 columnas).
    a, b = st.columns(2)
    a.metric("Precio actual", f"${metricas['precio_actual']:.2f}")
    b.metric("Variación periodo", f"{metricas['variacion_pct']:+.2f}%")
    c, d = st.columns(2)
    c.metric("Volatilidad anual", f"{metricas['volatilidad_anual_pct']:.2f}%")
    d.metric("Stop-loss / Take-profit",
             f"${metricas['stop_loss']:.2f} / ${metricas['take_profit']:.2f}")

    try:
        senal, motivo = generar_senal(df)
        if senal == "COMPRAR":
            st.success(f"📈 **{senal}** — {motivo}")
        elif senal == "VENDER":
            st.error(f"📉 **{senal}** — {motivo}")
        else:
            st.warning(f"⏸️ **{senal}** — {motivo}")
        st.caption("_Señal educativa, no es asesoría financiera real._")
    except (IndexError, KeyError):
        st.warning("No hay suficientes datos para generar una señal.")

    st.plotly_chart(grafica_precio_smas(df, simbolo), use_container_width=True)
    st.plotly_chart(grafica_rsi(df), use_container_width=True)

    with st.expander("Últimos 30 días"):
        cols_visibles = [c for c in
                         ["Open", "High", "Low", "Close", "Volume", "SMA_20", "SMA_50", "RSI_14"]
                         if c in df.columns]
        st.dataframe(df[cols_visibles].tail(30).round(2), use_container_width=True)


# ---------------------------------------------------------------------------
# Pantalla Portfolio (tenencias + transacciones)
# ---------------------------------------------------------------------------

def pantalla_portafolio() -> None:
    usuario = st.session_state["usuario"]
    ruta = ruta_portafolio_usuario(usuario)
    estado = cargar_portafolio(ruta)
    tenencias = calcular_tenencias(estado)

    # Valoración a precio de mercado.
    filas: list[dict] = []
    valor_tenencias = 0.0
    for sim, t in tenencias.items():
        precio = precio_actual_simbolo(sim) or t["precio_promedio"]
        valor_mercado = t["cantidad"] * precio
        valor_tenencias += valor_mercado
        pnl_abs = valor_mercado - t["costo_total"]
        pnl_pct = (pnl_abs / t["costo_total"]) * 100 if t["costo_total"] else 0.0
        filas.append({
            "Símbolo": sim,
            "Cant.": t["cantidad"],
            "Promedio": round(t["precio_promedio"], 2),
            "Actual": round(precio, 2),
            "Mercado": round(valor_mercado, 2),
            "P&L $": round(pnl_abs, 2),
            "P&L %": round(pnl_pct, 2),
        })

    saldo = estado["saldo_usd"]
    valor_total = saldo + valor_tenencias
    pnl_total = valor_total - SALDO_INICIAL_USD
    pnl_total_pct = (pnl_total / SALDO_INICIAL_USD) * 100

    st.markdown("### 💼 Mi Portafolio")
    a, b = st.columns(2)
    a.metric("Saldo en efectivo", f"${saldo:,.2f}")
    b.metric("Valor de tenencias", f"${valor_tenencias:,.2f}")
    c, d = st.columns(2)
    c.metric("Valor total", f"${valor_total:,.2f}")
    d.metric("P&L total", f"${pnl_total:+,.2f}", delta=f"{pnl_total_pct:+.2f}%")

    st.divider()
    st.markdown("#### Registrar transacción")
    with st.form("form_tx", clear_on_submit=True):
        sim_in = st.text_input("Símbolo", value="AAPL").upper().strip()
        cols = st.columns(2)
        tipo_in = cols[0].selectbox("Tipo", ["COMPRA", "VENTA"])
        cantidad_in = cols[1].number_input("Cantidad", min_value=1, step=1, value=1)
        cols2 = st.columns(2)
        precio_in = cols2[0].number_input(
            "Precio (USD)", min_value=0.01, step=0.01, value=100.00, format="%.2f"
        )
        fecha_in = cols2[1].date_input("Fecha", value=date.today(), max_value=date.today())
        enviar = st.form_submit_button("Registrar", type="primary", use_container_width=True)

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
            st.success(f"Transacción {tipo_in} de {cantidad_in} {sim_in} registrada.")
            st.rerun()
        except TransaccionInvalida as exc:
            st.error(str(exc))

    st.divider()
    st.markdown("#### Tenencias actuales")
    if filas:
        st.dataframe(pd.DataFrame(filas), use_container_width=True, hide_index=True)
    else:
        st.info("Aún no tienes posiciones. Registra una compra para empezar.")

    st.markdown("#### Histórico de transacciones")
    if estado["transacciones"]:
        df_tx = pd.DataFrame(estado["transacciones"])
        st.dataframe(df_tx, use_container_width=True, hide_index=True)
        if st.button("↩️ Deshacer última transacción", use_container_width=True):
            historico_recortado = estado["transacciones"][:-1]
            recompuesto = {"saldo_usd": SALDO_INICIAL_USD, "transacciones": []}
            for tx in historico_recortado:
                recompuesto = aplicar_transaccion(recompuesto, tx)
            guardar_portafolio(ruta, recompuesto)
            st.rerun()
    else:
        st.info("Aún no hay transacciones registradas.")


# ---------------------------------------------------------------------------
# Pantalla Learn (contenido educativo)
# ---------------------------------------------------------------------------

def pantalla_learn() -> None:
    st.markdown("### 📚 Aprende")
    st.caption("Conceptos clave para entender las señales del prototipo.")

    st.markdown(
        f"""
        <div class="iv-card">
            <h4 style="margin-top:0;">📈 Media Móvil Simple (SMA)</h4>
            <p>Promedio del precio de cierre en una ventana de tiempo.
            Cuando la <b>SMA20</b> (corto plazo) cruza por encima de la
            <b>SMA50</b> (largo plazo) es señal de <b>tendencia alcista</b>;
            cuando cruza por debajo, suele indicar tendencia bajista.</p>
        </div>

        <div class="iv-card">
            <h4 style="margin-top:0;">⚖️ Índice de Fuerza Relativa (RSI)</h4>
            <p>Mide la velocidad y magnitud de los cambios de precio
            (escala 0–100).</p>
            <ul>
              <li><b>RSI &gt; 70</b>: posible <b>sobrecompra</b> — el activo
              podría estar caro.</li>
              <li><b>RSI &lt; 30</b>: posible <b>sobreventa</b> — podría estar
              barato.</li>
              <li><b>30–70</b>: zona neutra.</li>
            </ul>
        </div>

        <div class="iv-card">
            <h4 style="margin-top:0;">🎯 Cómo se generan las señales</h4>
            <table style="width:100%; font-size:0.9rem;">
              <tr style="text-align:left; color:{COLOR_TEXTO_MUTED};">
                <th>Condición</th><th>Señal</th>
              </tr>
              <tr>
                <td>SMA20 &gt; SMA50 <i>y</i> RSI &lt; 70</td>
                <td>{html_badge('COMPRAR')}</td>
              </tr>
              <tr>
                <td>SMA20 &lt; SMA50 <i>o</i> RSI &gt; 70</td>
                <td>{html_badge('VENDER')}</td>
              </tr>
              <tr>
                <td>cualquier otro caso</td>
                <td>{html_badge('MANTENER')}</td>
              </tr>
            </table>
        </div>

        <div class="iv-card">
            <h4 style="margin-top:0;">💡 Volatilidad anualizada</h4>
            <p>Mide cuánto tiende a fluctuar el precio.
            Calculada como la desviación estándar de los retornos diarios
            multiplicada por √252 (días hábiles del año). Mayor volatilidad
            = más riesgo y más oportunidad.</p>
        </div>

        <div class="iv-card" style="background:{COLOR_FONDO_SUAVE};">
            <h4 style="margin-top:0;">⚠️ Recordatorio</h4>
            <p style="margin-bottom:0;">Estas reglas son <b>educativas</b>.
            Los analistas profesionales combinan muchas más variables:
            fundamentales de la empresa, contexto macroeconómico, eventos
            geopolíticos, fiscalidad, etc. <b>No es asesoría financiera.</b></p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button("Probar el análisis técnico →", type="primary",
                 use_container_width=True):
        st.session_state.screen = "analysis"
        st.session_state.pop("simbolo_seleccionado", None)
        st.rerun()


# ---------------------------------------------------------------------------
# Pantalla Profile
# ---------------------------------------------------------------------------

def pantalla_profile() -> None:
    usuario = st.session_state["usuario"]

    st.markdown("### 👤 Perfil")
    st.markdown(
        f"""
        <div class="iv-card" style="text-align:center;">
            <div style="
                width:80px; height:80px; margin:0.5rem auto 1rem auto;
                background:{COLOR_PRIMARIO}; border-radius:50%;
                display:flex; align-items:center; justify-content:center;
                color:white; font-size:32px; font-weight:700;">
                {usuario[0].upper()}
            </div>
            <div style="font-weight:700; font-size:1.2rem;">{usuario}</div>
            <div style="color:{COLOR_TEXTO_MUTED}; font-size:0.9rem;">
                Sesión activa
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("### Acerca del prototipo")
    st.markdown(
        f"""
        <div class="iv-card">
            <p>Prototipo académico (TRL5) del trabajo de grado
            <b>"Sistema de apoyo a la toma de decisiones en inversión
            bursátil basado en datos históricos"</b>.</p>
            <p style="color:{COLOR_TEXTO_MUTED}; font-size:0.85rem;">
            Datos: Yahoo Finance · Indicadores: SMA20, SMA50, RSI14 ·
            Persistencia local en JSON.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.warning(DISCLAIMER)

    if st.button("Cerrar sesión", type="primary", use_container_width=True):
        st.session_state.clear()
        st.rerun()


# ---------------------------------------------------------------------------
# Bottom navigation y router principal
# ---------------------------------------------------------------------------

# Bottom nav alineado con el Figma de InvestIA: 4 tabs.
# El Análisis técnico es una pantalla "interior" a la que se llega desde
# las recomendaciones del Home o desde Learn, no desde el bottom nav.
ITEMS_NAV = [
    ("🏠", "Home", "home"),
    ("💼", "Portfolio", "portfolio"),
    ("📚", "Learn", "learn"),
    ("👤", "Profile", "profile"),
]

PANTALLAS = {
    "home": pantalla_home,
    "portfolio": pantalla_portafolio,
    "learn": pantalla_learn,
    "profile": pantalla_profile,
    "analysis": pantalla_analisis,  # accesible solo via cards/Learn
}


def render_bottom_nav() -> None:
    """Barra inferior con 4 botones. La columna activa usa botón primario azul."""
    st.markdown('<div class="iv-bottom-nav">', unsafe_allow_html=True)
    cols = st.columns(len(ITEMS_NAV))
    activa = st.session_state.get("screen", "home")
    for col, (icono, etiqueta, screen_id) in zip(cols, ITEMS_NAV):
        es_activa = screen_id == activa
        if col.button(
            f"{icono} {etiqueta}",
            key=f"nav_{screen_id}",
            type="primary" if es_activa else "secondary",
            use_container_width=True,
        ):
            st.session_state.screen = screen_id
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)


def main() -> None:
    st.set_page_config(
        page_title="InvestIA",
        page_icon="📈",
        layout="centered",
        initial_sidebar_state="collapsed",
    )
    inyectar_css()

    # Si no hay usuario logueado, mostramos solo el flujo de auth.
    if "usuario" not in st.session_state:
        pagina_autenticacion()
        return

    # Pantalla actual (default Home). Envolvemos en try/except para que un
    # error en una pantalla nunca esconda la barra inferior de navegación.
    screen = st.session_state.setdefault("screen", "home")
    try:
        PANTALLAS.get(screen, pantalla_home)()
    except Exception as exc:
        st.error(f"Error al renderizar la pantalla '{screen}': {exc}")

    # Bottom nav siempre visible (excepto en pantalla de auth).
    render_bottom_nav()


if __name__ == "__main__":
    main()
