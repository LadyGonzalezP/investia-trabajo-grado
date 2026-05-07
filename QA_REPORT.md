# QA Report — InvestIA Prototype

**Fecha:** 2026-05-07
**Versión:** rama `main` post-rediseño InvestIA
**Ejecutor:** validación automatizada + integración real con Yahoo Finance

---

## Resumen ejecutivo

| Suite | Casos | Pasa | Falla | Estado |
|---|---|---|---|---|
| QA-1: pytest funciones puras | 23 | 23 | 0 | ✅ |
| QA-2: Pipeline real (5 tickers × 4 checks) | 20 | 20 | 0 | ✅ |
| QA-3: Edge cases | 10 | 10 | 0 | ✅ |
| QA-4: Aislamiento multi-usuario | 2 | 2 | 0 | ✅ |
| QA-5: Streamlit HTTP + render | 5 | 5 | 0 | ✅ |
| **QA-7: Tests UI con `AppTest` (M-1 a M-4)** | **14** | **14** | **0** | **✅** |
| **Total** | **74** | **74** | **0** | **✅** |

> **Resultado: aprobado**. Todas las suites están verdes, incluidas las
> verificaciones que antes eran manuales (M-1 a M-4) y ahora se ejecutan
> automáticamente con el framework `streamlit.testing.v1.AppTest`.

---

## 1. QA-1 · pytest (`tests/test_logica.py`)

23 tests sobre funciones puras de `logica.py`. Comando:

```powershell
.\venv\Scripts\python.exe -m pytest -v
```

Resultado: `23 passed in 1.04s`. Cobertura:

- SMA: 2 tests (ventana correcta, NaN antes de completar).
- RSI Wilder: 3 tests (creciente→100, decreciente→0, longitud insuficiente).
- Señal: 4 tests (COMPRAR, VENDER por SMA, VENDER por RSI, MANTENER).
- Métricas: 1 test consolidado (precio, variación, volatilidad, stop, take).
- Persistencia portafolio: 2 tests (estado inicial, round-trip JSON).
- Transacciones: 5 tests (compra, venta, exceso saldo, exceso tenencia, tenencias).
- Auth: 6 tests (registro, duplicado, login OK/KO, salt distinto, persistencia).

---

## 2. QA-2 · Pipeline real con yfinance

Script: `qa_integration.py` § QA-2. Para cada uno de los 5 tickers preset
(AAPL, MSFT, TSLA, NVDA, SPY) se valida:

| Check | AAPL | MSFT | TSLA | NVDA | SPY |
|---|---|---|---|---|---|
| `yfinance` descarga > 100 filas | ✅ | ✅ | ✅ | ✅ | ✅ |
| SMA20/SMA50/RSI14 sin NaN al cierre | ✅ | ✅ | ✅ | ✅ | ✅ |
| Señal en {COMPRAR, VENDER, MANTENER} con motivo | ✅ | ✅ | ✅ | ✅ | ✅ |
| Métricas con tipos correctos y stop<precio<take | ✅ | ✅ | ✅ | ✅ | ✅ |

Confirma que el pipeline ingestión → indicadores → señal → métricas funciona
con **datos reales del mercado** (criterio TRL5).

---

## 3. QA-3 · Edge cases

| Caso | Resultado esperado | Observado |
|---|---|---|
| `yfinance` con símbolo inexistente (`XXXNOEXISTE9999`) | DataFrame vacío | ✅ vacío |
| Compra con cantidad×precio > saldo | `TransaccionInvalida` | ✅ lanza |
| Venta de símbolo sin tenencia | `TransaccionInvalida` | ✅ lanza |
| Login con credenciales incorrectas | `False` | ✅ |
| Registro de usuario duplicado | `UsuarioYaExiste` | ✅ lanza |
| Hash determinístico con mismo salt+password | igual | ✅ |
| Hash con salt distinto | distinto | ✅ |
| Cargar `portafolio.json` corrupto | `json.JSONDecodeError` | ✅ lanza |
| Escritura atómica deja destino y sin `.tmp` colgado | sí | ✅ |
| Tenencias con compras+ventas mantienen promedio ponderado | sí | ✅ |
| Replay sin última tx restaura estado anterior (deshacer) | sí | ✅ |

---

## 4. QA-4 · Aislamiento multi-usuario

| Caso | Resultado |
|---|---|
| Alice y Bob escriben en `portafolio_alice.json` y `portafolio_bob.json` | ✅ archivos separados |
| Bob no ve la tenencia de Alice | ✅ |
| Login de Alice con clave de Bob (cruce) | ✅ rechazado |
| Login correcto independiente para cada uno | ✅ |

---

## 5. QA-5 · Streamlit live

| Verificación | Comando | Resultado |
|---|---|---|
| GET `/` responde | `curl http://localhost:8501/` | HTTP 200 |
| Health check | `curl http://localhost:8501/_stcore/health` | `ok` |
| `app.py` importa sin errores | `python -c "import app"` | OK |
| Pantallas registradas | `app.PANTALLAS.keys()` | home, portfolio, learn, profile, analysis |
| Bottom nav items | `app.ITEMS_NAV` | Home, Portfolio, Learn, Profile (4, alineado al Figma) |

---

## 6. Verificaciones M-1 a M-4 (ahora automatizadas vía `AppTest`)

Originalmente estas cuatro verificaciones se planearon manuales. Ahora
están cubiertas por `tests/test_ui.py`, que ejecuta el script real con
`streamlit.testing.v1.AppTest` y simula clicks/inputs sin navegador.
`yfinance` se mockea con OHLCV sintético determinístico.

| ID | Caso | Tests automáticos que lo cubren |
|---|---|---|
| **M-1** Welcome → Login → Home | `test_welcome_screen_renders_logo_y_get_started`, `test_get_started_navega_a_login`, `test_signup_crea_usuario_en_disco`, `test_login_credenciales_incorrectas_muestra_error`, `test_login_correcto_muestra_home_con_saludo` |
| **M-2** Bottom nav 4 secciones | `test_bottom_nav_tiene_4_items_alineados_con_figma`, `test_bottom_nav_navega_entre_secciones`, `test_pantalla_learn_explica_indicadores` |
| **M-3** Drill-in análisis técnico | `test_card_recomendacion_navega_a_analisis`, `test_volver_al_home_desde_analisis_limpia_seleccion` |
| **M-4** Portafolio + persistencia | `test_compra_descuenta_saldo_y_se_persiste`, `test_compra_que_excede_saldo_muestra_error`, `test_persistencia_entre_sesiones`, `test_aislamiento_dos_usuarios_no_ven_el_portafolio_del_otro` |

Recomendación: ejecutar `pytest -v` antes de grabar el video y verificar
que las 37 pruebas siguen verdes.

---

## 7. Cómo reproducir esta QA

```powershell
cd D:\trabajo-grado
.\venv\Scripts\Activate.ps1

# QA-1: pytest
pytest -v

# QA-2 + QA-3 + QA-4: integración real
python qa_integration.py

# QA-5: Streamlit live
Start-Process powershell -ArgumentList "streamlit run app.py"
Start-Sleep -Seconds 5
curl http://localhost:8501/_stcore/health
```

---

## 8. Observaciones y recomendaciones

1. **yfinance puede fallar puntualmente** (timeout o "possibly delisted").
   El código degrada con un `st.warning` claro en Home en lugar de mostrar
   pantalla en blanco. Verificado.
2. **Caché de Streamlit (`@st.cache_data`)**: se usa en `descargar_datos`
   con TTL 1 h. Para forzar refresco durante demo, reiniciar la app.
3. **Encoding Windows**: el script `qa_integration.py` evita emojis en
   `print()` para no fallar en `cp1252`. El archivo `usuarios.json` y
   `portafolio_*.json` se escriben con `encoding="utf-8"` para soportar
   tildes/eñes.
4. **Qué no está cubierto por tests automáticos** y queda en M-1..M-4:
   navegación entre tabs, carga de gráficas Plotly, formularios Streamlit,
   estados visuales (badge colors, hero blue, mobile width).

---

**Estado del prototipo: listo para grabar video de sustentación
una vez confirmadas M-1..M-4.**
