# SPEC.md — Sistema de apoyo a la toma de decisiones en inversión bursátil

## 1. Objetivo y usuarios

### 1.1 Objetivo

Construir un **prototipo académico funcional (TRL5)** que apoye la toma de decisiones de inversión bursátil mediante:

- Análisis técnico básico sobre datos históricos reales (yfinance).
- Generación de señales educativas (COMPRAR / VENDER / MANTENER).
- **Gestión de un portafolio personal simulado**, con saldo en USD y registro de transacciones, persistente entre ejecuciones.
- **Autenticación simple multi-usuario** (registro y login con contraseñas hasheadas) para que cada usuario maneje su propio portafolio.

No ejecuta operaciones reales en brokers. No conecta a ningún sistema externo más allá de la API pública de Yahoo Finance. No usa base de datos: todo en archivos JSON locales.

### 1.2 Usuarios objetivo

| Usuario | Necesidad |
|---|---|
| Estudiante (autor) | Demostrar prototipo en sustentación, video ≤ 10 min, código explicable. |
| Jurado / asesor | Validar funcionalidad y nivel TRL5 sin instalar dependencias complejas. |
| Audiencia académica | Entender el flujo análisis → señal → decisión registrada. |

### 1.3 Definición de TRL5 aplicada

Tecnología validada en entorno relevante: el sistema integra ingestión real (yfinance), procesamiento (pandas/numpy), análisis técnico, visualización interactiva (plotly/streamlit), portafolio persistente y autenticación local. Validado con datos reales de mercado contra fuentes externas (TradingView, Yahoo Finance), sin alcanzar TRL6/7 (no operación productiva con usuarios reales ni conexión a brokers).

---

## 2. Alcance funcional (features y criterios de aceptación)

### F1 — Análisis histórico de un símbolo

- AC1.1 El usuario puede ingresar cualquier símbolo válido (input libre + presets AAPL, MSFT, TSLA, NVDA, SPY).
- AC1.2 El usuario puede seleccionar fecha de inicio y fin con `st.date_input` (validación: inicio < fin).
- AC1.3 La app descarga datos con `yfinance` y los muestra en una tabla (`st.dataframe`).
- AC1.4 Si el símbolo no existe o no devuelve datos, se muestra `st.error` claro y se detiene la ejecución.
- AC1.5 La descarga se cachea con `@st.cache_data(ttl=3600)`.

### F2 — Indicadores técnicos

- AC2.1 SMA 20 días sobre el precio de cierre.
- AC2.2 SMA 50 días sobre el precio de cierre.
- AC2.3 RSI 14 días (Wilder, sin librerías externas).
- AC2.4 Si el rango tiene < 50 filas válidas, `st.warning` indicando que las medias móviles aún no son significativas (no bloquea).

### F3 — Señal educativa

| Condición sobre la última fila válida | Señal | Render |
|---|---|---|
| `SMA_20 > SMA_50` y `RSI < 70` | COMPRAR | `st.success` |
| `SMA_20 < SMA_50` o `RSI > 70` | VENDER | `st.error` |
| Otro caso | MANTENER | `st.warning` |

- AC3.1 Junto a la señal se muestra el **motivo** con valores numéricos.
- AC3.2 Disclaimer permanente: *"Señal educativa, no es asesoría financiera real."*

### F4 — Métricas

KPIs en `st.columns(5)`:

| Métrica | Cálculo |
|---|---|
| Precio actual | Último `Close` |
| Variación % del periodo | `(Close[-1] / Close[0] - 1) * 100` |
| Volatilidad anualizada | `retornos_diarios.std() * sqrt(252) * 100` |
| Stop-loss sugerido | `precio_actual * 0.95` |
| Take-profit sugerido | `precio_actual * 1.10` |

### F5 — Visualización

- AC5.1 Gráfica Plotly: precio cierre + SMA20 + SMA50, leyenda interactiva.
- AC5.2 Gráfica Plotly RSI con líneas de referencia 30/70.
- AC5.3 Tabla de los últimos 30 días (Fecha, Open, High, Low, Close, Volume, SMA20, SMA50, RSI14).

### F6 — Portafolio personal con persistencia

**Estado inicial por usuario:** saldo USD 10.000, sin posiciones. Tras la primera transacción se crea `portafolio_<usuario>.json`.

- AC6.1 Pestaña "Mi portafolio" separada del análisis.
- AC6.2 Formulario para registrar transacción: símbolo, tipo (COMPRA / VENTA), cantidad (entero positivo), precio unitario (float positivo), fecha (≤ hoy).
- AC6.3 Validaciones: compra requiere `cantidad * precio ≤ saldo`; venta requiere `cantidad ≤ tenencia` (sin shorting).
- AC6.4 Tabla de transacciones con botón "Deshacer última transacción".
- AC6.5 Tabla de tenencias: símbolo, cantidad, precio promedio compra, precio actual (yfinance), valor de mercado, P&L absoluto, P&L %.
- AC6.6 KPIs en `st.columns(4)`: saldo en efectivo, valor de tenencias, valor total, P&L total.
- AC6.7 Persistencia: tras cada operación, `portafolio_<usuario>.json` se reescribe atómicamente.

### F7 — Disclaimer académico

- AC7.1 Banner permanente en cabecera y pie:
  > *"Prototipo académico (TRL5). No es asesoría financiera. No ejecuta operaciones reales."*

### F8 — Documentación

- AC8.1 `README.md` con 10 secciones del enunciado, en español, justificación TRL5 incluida.

### F9 — Autenticación simple multi-usuario

**Almacenamiento:** `usuarios.json` con shape:
```json
[
  {"usuario": "lady", "salt": "ab12...", "hash": "9f3e...", "creado": "2026-05-07"}
]
```

- AC9.1 Pantalla inicial muestra dos tabs: "Iniciar sesión" / "Crear cuenta".
- AC9.2 Crear cuenta: usuario alfanumérico (3–20 chars), contraseña ≥ 6 chars. Rechaza usuarios duplicados con `st.error`.
- AC9.3 Iniciar sesión: valida credenciales contra hash. Credenciales incorrectas → `st.error`, sin pista sobre qué falló.
- AC9.4 Tras login exitoso, `st.session_state.usuario` queda fijado y la app muestra Análisis + Mi portafolio.
- AC9.5 Sidebar muestra usuario activo y botón "Cerrar sesión" que limpia `session_state` y vuelve a la pantalla de login.
- AC9.6 Hashing con `hashlib.sha256` + salt aleatorio de 16 bytes (`secrets.token_hex(16)`). **Nunca** se guarda la contraseña en claro.
- AC9.7 Cada usuario solo ve y modifica `portafolio_<usuario>.json`. Imposible acceder a otro portafolio sin login.

---

## 3. Tecnologías, comandos y estructura

### 3.1 Stack

| Capa | Tecnología | Versión mínima |
|---|---|---|
| Lenguaje | Python | 3.11 |
| UI | Streamlit | ≥ 1.32 |
| Datos de mercado | yfinance | ≥ 0.2.40 |
| Procesamiento | pandas | ≥ 2.1 |
| Cálculo numérico | numpy | ≥ 1.26 |
| Visualización | plotly | ≥ 5.20 |
| Persistencia | JSON nativo + `hashlib`/`secrets` (stdlib) | — |
| Tests | pytest | ≥ 8.0 (dev) |

### 3.2 Estructura del proyecto

```
D:\trabajo-grado\
├── app.py                    # Aplicación Streamlit (UI + auth + portafolio + análisis)
├── logica.py                 # Funciones puras: indicadores, señal, métricas, transacciones, hashing
├── tests\
│   └── test_logica.py        # pytest unitarios
├── requirements.txt          # Runtime
├── requirements-dev.txt      # + pytest
├── README.md                 # Documentación académica
├── SPEC.md                   # Este documento
├── .gitignore                # Ignora venv/, __pycache__/, *.json de usuario
├── usuarios.json             # (runtime, NO se sube) usuarios + hashes
└── portafolio_<usuario>.json # (runtime, NO se sube) portafolio por usuario
```

### 3.3 Comandos del proyecto

```powershell
cd D:\trabajo-grado
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
pytest -q                     # tests verdes
streamlit run app.py          # arrancar UI
deactivate
```

---

## 4. Estilo de código

- Idioma español: comentarios, identificadores y UI.
- Type hints en todas las funciones.
- Funciones puras separadas en `logica.py` (sin `st.*` ni I/O salvo cargar/guardar JSON).
- Sin clases innecesarias. Estado del portafolio = `dict`.
- Comentarios solo cuando explican el *por qué*.
- Validación solo en bordes (input usuario, descarga yfinance, lectura JSON).
- Cacheo `@st.cache_data` solo en `descargar_datos`. Nunca en funciones que tocan JSON.

---

## 5. Estrategia de testing

**Doble capa:**

1. **TDD automatizado con pytest** sobre `logica.py` (funciones puras).
2. **Validación manual documentada** sobre la UI (yfinance + Streamlit).

### 5.1 Tests automatizados (pytest)

- SMA: ventana correcta, NaN antes de completar.
- RSI: ≈100 para serie creciente, ≈0 para decreciente, NaN si longitud < periodo.
- Señal: 4 escenarios (comprar / vender SMA / vender RSI / mantener).
- Métricas: variación, volatilidad, stop, take.
- Portafolio: cargar inexistente → estado inicial; round-trip JSON; compra; venta; compra excede saldo (lanza); venta excede tenencia (lanza); cálculo de tenencias.
- Auth: hash determinístico con salt, registro nuevo OK, registro duplicado lanza, login correcto, login incorrecto, password nunca queda plana.

### 5.2 Validación manual

| # | Caso | Resultado esperado |
|---|---|---|
| T1 | AAPL, últimos 2 años | Tabla, gráficas SMA/RSI, señal coherente. |
| T2 | Símbolo inválido | `st.error` claro, sin traceback. |
| T3 | Rango 5 días | `st.warning` por SMA insuficiente. |
| T4 | Fecha inicio > fin | `st.error`. |
| T5 | RSI vs. TradingView | Diferencia < 0.5. |
| T6 | Compra AAPL ×10 a 187.45 | Saldo −1874.50, tenencia AAPL=10. |
| T7 | Venta AAPL ×5 | Saldo +5×precio, tenencia AAPL=5. |
| T8 | Venta sin tenencia | `st.error`. |
| T9 | Compra excede saldo | `st.error`. |
| T10 | Cerrar app y reabrir | Portafolio del usuario persiste. |
| T11 | Botón deshacer | Última transacción se elimina, saldo y tenencia recalculados. |
| T12 | Crear cuenta nueva | `usuarios.json` registra usuario+salt+hash. Login posterior funciona. |
| T13 | Crear cuenta con usuario existente | `st.error`. |
| T14 | Login con password incorrecta | `st.error`, no hay pista. |
| T15 | Dos usuarios distintos | Cada uno ve su propio portafolio; no puede ver el del otro. |

---

## 6. Boundaries

### 6.1 Siempre

- Mantener single-file de UI (`app.py`) + `logica.py`.
- Comentarios y UI en español.
- Disclaimer académico permanente.
- Validar entradas en el borde.
- Persistir tras cada operación, atómicamente.
- Hashear contraseñas con sha256+salt; nunca guardarlas en claro.

### 6.2 Preguntar antes

- Añadir indicadores adicionales (MACD, Bollinger).
- Cambiar la lógica de señales.
- Convertir saldo a otra moneda.
- Añadir backtesting cuantitativo.
- Subir `*.json` (usuarios o portafolios) al repositorio.

### 6.3 Nunca

- Conectar a brokers reales ni ejecutar órdenes.
- Usar bases de datos (SQLite, Postgres, Mongo).
- OAuth, JWT, sesiones server-side, "recordarme" persistente.
- Pasarela de pagos.
- APIs privadas con keys.
- Machine learning.
- Arquitectura multi-capa (backend separado, microservicios).
- Inventar datos: si yfinance falla, mostrar error.
- Sobre-ingeniería.

---

## 7. Plan de tareas (TDD: RED → GREEN → REFACTOR)

### T0 — Setup
- Crear estructura, requirements, .gitignore, SPEC.md, README placeholder.
- `git init` + commit inicial.
- venv + `pip install -r requirements-dev.txt`. `pytest` corre con 0 tests.

### T1 — SMA (TDD)
- `logica.calcular_smas(df, ventanas=(20,50)) -> pd.DataFrame`. 2 tests.

### T2 — RSI (TDD)
- `logica.calcular_rsi(serie, periodo=14) -> pd.Series` (Wilder). 3 tests.

### T3 — Señal (TDD)
- `logica.generar_senal(df) -> tuple[str, str]`. 4 tests.

### T4 — Métricas (TDD)
- `logica.calcular_metricas(df) -> dict`. 1 test consolidado.

### T5 — Portafolio cargar/guardar (TDD)
- `cargar_portafolio(ruta)`, `guardar_portafolio(ruta, estado)`. 2 tests con `tmp_path`.

### T6 — Transacciones (TDD)
- `aplicar_transaccion(estado, tx)`, `calcular_tenencias(estado)`. 5 tests, funciones inmutables.

### T6.5 — Autenticación (TDD)
- `hash_password`, `cargar_usuarios`, `guardar_usuarios`, `registrar_usuario`, `verificar_credenciales`. 5 tests con `tmp_path`.

### T7 — `descargar_datos` en `app.py`
- Wrapper `@st.cache_data` sobre `yfinance.download`. Verificación manual.

### T8 — UI Tab Análisis
- `set_page_config`, banner, tabs, sidebar, KPIs, señal coloreada, gráficas Plotly, tabla 30 días.

### T8.5 — UI Login/Registro
- Pantalla inicial con tabs Iniciar sesión / Crear cuenta. Tras login, fija `st.session_state.usuario` y nombra `portafolio_<usuario>.json`. Botón cerrar sesión.

### T9 — UI Tab Mi Portafolio
- KPIs, formulario nueva transacción, tabla tenencias con precios actuales, histórico, deshacer.

### T10 — README y verificación final
- 10 secciones del README. `pytest -q` verde, T1–T15 manuales.

### Definition of Done
- Todos los tests pytest verdes.
- Casos manuales T1–T15 documentados.
- Streamlit arranca sin errores en venv limpio.
- README, SPEC, .gitignore presentes.
- Commits atómicos por tarea.
