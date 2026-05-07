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
| **Total** | **60** | **60** | **0** | **✅** |

> **Resultado: aprobado**. Toda la lógica testeable automáticamente está verde
> y la app responde en `localhost:8501`. Quedan 4 verificaciones manuales
> que requieren navegador (ver §6).

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

## 6. Verificaciones manuales pendientes (UI)

Estas 4 verificaciones requieren un navegador y **deben hacerse antes de
grabar el video de sustentación**. Marca cada una al confirmar:

- [ ] **M-1 Welcome → Login → Home:** desde la pantalla Welcome con "Get
  started", llegar a Home logueado y ver el hero azul "Hola, &lt;usuario&gt;",
  el card del portafolio con el valor total, y al menos 3 cards de
  recomendaciones con badge Buy/Hold/Sell.
- [ ] **M-2 Bottom nav 4 secciones:** tocar cada uno de Home / Portfolio /
  Learn / Profile y verificar que la pantalla cambia correctamente. El botón
  activo debe estar en azul primario.
- [ ] **M-3 Drill-in al análisis técnico:** desde una card de recomendación
  en Home, tocar "Ver análisis técnico de AAPL →" y verificar que se abre
  la pantalla Análisis con AAPL preseleccionado, gráficas SMA y RSI, y
  botón "← Volver al Home".
- [ ] **M-4 Flujo portafolio + persistencia:** registrar una compra de
  AAPL desde Portfolio, ver que el saldo baja y la tenencia aparece. Cerrar
  sesión, volver a entrar y confirmar que la transacción persiste en
  `portafolio_<usuario>.json`.

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
