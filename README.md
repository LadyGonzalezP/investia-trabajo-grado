# Sistema de apoyo a la toma de decisiones en inversión bursátil

Prototipo académico (TRL5) desarrollado como trabajo de grado. Es una
aplicación web de una sola capa, escrita en Python con Streamlit, que apoya
la toma de decisiones en inversión bursátil a partir de **datos históricos
reales** descargados de Yahoo Finance.

> ⚠️ **Aviso académico:** este sistema **no constituye asesoría financiera**
> y **no ejecuta operaciones reales**. Todas las señales y métricas son
> educativas. Cualquier decisión de inversión real es responsabilidad
> exclusiva del usuario.

---

## 1. Descripción del proyecto

La aplicación cubre dos flujos complementarios:

1. **Análisis técnico** de un símbolo bursátil (AAPL, MSFT, TSLA, NVDA, SPY u
   otro):
   - Descarga de OHLCV histórico con `yfinance`.
   - Cálculo de **medias móviles simples** SMA20 y SMA50.
   - Cálculo del **Índice de Fuerza Relativa** (RSI 14, suavizado tipo Wilder).
   - Generación de una **señal educativa** COMPRAR / VENDER / MANTENER.
   - **Métricas** del periodo: precio actual, variación %, volatilidad anual,
     stop-loss y take-profit sugeridos.
   - Gráficas interactivas Plotly y tabla de los últimos 30 días.

2. **Portafolio personal simulado** con persistencia local:
   - Saldo inicial USD 10.000 por usuario.
   - Registro manual de transacciones de compra y venta.
   - Tabla de tenencias actuales valoradas con el precio actual de yfinance.
   - KPIs del portafolio (efectivo, valor de mercado, valor total, P&L).
   - Botón **deshacer última transacción**.
   - Cada usuario tiene su propio archivo `portafolio_<usuario>.json`.

La aplicación incluye **autenticación local simple** con SHA-256 + salt
aleatorio por usuario, persistida en `usuarios.json`. Las contraseñas nunca
se almacenan en claro.

---

## 2. Alcance académico (TRL5)

Este prototipo demuestra **TRL5 — tecnología validada en entorno relevante**
porque integra de forma funcional varios componentes en condiciones reales
sin alcanzar producción:

| Componente | Tecnología validada en entorno relevante |
|---|---|
| Ingestión de datos | yfinance contra Yahoo Finance, datos de mercado reales. |
| Procesamiento numérico | pandas / numpy con indicadores técnicos estándar. |
| Lógica de decisión | reglas determinísticas validadas con pytest (RED-GREEN). |
| Persistencia | archivos JSON locales con escritura atómica (rename). |
| Autenticación | hash SHA-256 + salt por usuario, criterio mínimo viable. |
| Visualización | Plotly + Streamlit para una experiencia interactiva. |

**Lo que este prototipo intencionalmente NO hace** (define el límite con TRL6/7):
- No conecta a brokers ni ejecuta órdenes reales.
- No usa base de datos, OAuth, ni infraestructura productiva.
- No incorpora machine learning ni backtesting cuantitativo formal.
- No está validado por usuarios reales en producción continua.

---

## 3. Tecnologías usadas

| Capa | Tecnología | Propósito |
|---|---|---|
| Lenguaje | Python 3.11 | Base del prototipo |
| Interfaz | Streamlit ≥ 1.32 | App web sin frontend separado |
| Datos de mercado | yfinance ≥ 0.2.40 | Histórico OHLCV de Yahoo Finance |
| Procesamiento | pandas ≥ 2.1, numpy ≥ 1.26 | Series temporales e indicadores |
| Visualización | plotly ≥ 5.20 | Gráficas interactivas |
| Persistencia | módulos `json`, `pathlib` (stdlib) | Archivos JSON locales |
| Seguridad | módulos `hashlib`, `secrets` (stdlib) | SHA-256 + salt aleatorio |
| Tests | pytest ≥ 8.0 | TDD sobre funciones puras |

Sin frameworks pesados, sin bases de datos, sin servicios en la nube.

---

## 4. Instalación

Requisito previo: **Python 3.11 o superior** y **Git**.

Pasos en PowerShell (Windows):

```powershell
# Clonar el repositorio
git clone https://github.com/LadyGonzalezP/investia-trabajo-grado.git
cd investia-trabajo-grado

# Crear y activar entorno virtual
python -m venv venv
.\venv\Scripts\Activate.ps1

# Instalar dependencias (incluye pytest para los tests)
pip install -r requirements-dev.txt
```

> Si solo necesitas ejecutar la aplicación sin correr los tests, usa
> `pip install -r requirements.txt`.

---

## 5. Ejecución

Con el entorno virtual activado:

```powershell
# Correr los tests automatizados
pytest -q

# Arrancar la aplicación
streamlit run app.py
```

Streamlit abrirá automáticamente el navegador en
[http://localhost:8501](http://localhost:8501).

---

## 6. Uso paso a paso

1. **Crear cuenta:** en la primera ejecución aparece la pantalla de
   autenticación. Cambia a la pestaña **"Crear cuenta"**, ingresa un usuario
   alfanumérico (3–20 caracteres) y una contraseña (mínimo 6 caracteres).
2. **Iniciar sesión** con esas credenciales.
3. **Tab Análisis:**
   - Escribe un símbolo (`AAPL` por defecto) o elige uno de los presets.
   - Ajusta el rango de fechas (por defecto 2 años).
   - Lee las métricas, la señal coloreada y las dos gráficas interactivas.
4. **Tab Mi portafolio:**
   - Revisa los KPIs (saldo, tenencias, P&L).
   - Registra una compra o venta con el formulario.
   - Las tenencias se valoran al precio actual de Yahoo Finance.
   - Puedes deshacer la última transacción.
5. **Cerrar sesión** desde la barra lateral. El portafolio queda guardado en
   `portafolio_<usuario>.json` y se restaura al volver a iniciar sesión.

---

## 7. Estructura del repositorio

```
trabajo-grado/
├── app.py                # Aplicación Streamlit (UI + auth + flujo)
├── logica.py             # Funciones puras: indicadores, señal, métricas,
│                         #   transacciones, autenticación
├── tests/
│   └── test_logica.py    # 23 tests pytest (TDD)
├── requirements.txt      # Dependencias de runtime
├── requirements-dev.txt  # Runtime + pytest
├── pytest.ini            # Configuración pytest (pythonpath=.)
├── README.md             # Este documento
├── SPEC.md               # Especificación funcional completa
└── .gitignore            # Excluye venv, caches y archivos JSON de usuario
```

Archivos generados en tiempo de ejecución (gitignorados):

- `usuarios.json` — registros de usuarios con salt y hash SHA-256.
- `portafolio_<usuario>.json` — un archivo por usuario logueado.

---

## 8. Pruebas

El prototipo combina **dos estrategias de validación**:

### 8.1 Pruebas automatizadas (pytest)

23 tests sobre `logica.py` cubren las funciones puras:

```powershell
pytest -q
```

Áreas cubiertas:
- SMA: ventana correcta y NaN antes de completar.
- RSI Wilder: ≈100 en serie creciente, ≈0 en decreciente, NaN si longitud < periodo.
- Señal: cuatro escenarios COMPRAR / VENDER (SMA) / VENDER (RSI) / MANTENER.
- Métricas: variación, volatilidad, stop-loss, take-profit.
- Portafolio: estado inicial, persistencia atómica, compra, venta, validaciones,
  cálculo de tenencias por costo promedio ponderado.
- Auth: hash determinístico, salt distinto por usuario, registro duplicado,
  login correcto/incorrecto, persistencia.

### 8.2 Validación manual de la UI

Ejecutar antes de la grabación del video / sustentación. Lista en `SPEC.md`
(casos T1–T15): tickers válidos/inválidos, rango muy corto, fechas
inconsistentes, comparación cruzada del RSI con TradingView, flujo de compras
y ventas, deshacer, persistencia entre sesiones, registro y login.

---

## 9. Advertencia legal

Este sistema es un **prototipo académico**. Las señales mostradas
(COMPRAR / VENDER / MANTENER) y todas las métricas son **educativas** y se
basan en reglas técnicas simples. **NO constituyen asesoría financiera**,
no consideran tu perfil de riesgo, tu horizonte de inversión, costos de
transacción reales, fiscalidad ni dividendos. **El sistema no ejecuta
operaciones reales** y nunca debe usarse para tomar decisiones de inversión
sin el acompañamiento de un profesional certificado.

Los datos provienen de Yahoo Finance vía la librería `yfinance` y pueden
contener errores, retrasos o estar incompletos. El autor del trabajo de
grado no se responsabiliza por decisiones tomadas a partir de la información
mostrada por la aplicación.

---

## 10. Limitaciones conocidas y trabajo futuro

Limitaciones intencionales del prototipo (alineadas con TRL5):

- Sin conexión a brokers reales ni ejecución de órdenes.
- Sin base de datos: la persistencia es por archivos JSON locales.
- Autenticación mínima (sin OAuth, sin recuperación de contraseña, sin 2FA).
- Sin machine learning ni backtesting cuantitativo formal.
- Sin paginación: la tabla muestra los últimos 30 días.
- Solo USD: no hay conversión de moneda.
- Datos al cierre del día (no en tiempo real).

Posibles extensiones para fases futuras (TRL6+):

- Backtesting con métricas (Sharpe, drawdown).
- Indicadores adicionales (MACD, Bollinger).
- Conexión a un broker en modo paper trading.
- Despliegue en Streamlit Cloud o contenedor Docker.

---

## Autor

Trabajo de grado — Lady González (`lady.kgonzalez@gmail.com`).
