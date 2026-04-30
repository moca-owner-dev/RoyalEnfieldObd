# Royal Enfield Interceptor 650 — Estado Completo del Proyecto

**Última actualización:** 2026-04-26 (sesión: armado de stack web + captura de dataset)
**Working directory:** `/home/pipboy/Descargas/RoyalEnfieldObd/`

---

## 🎯 Objetivo

La moto del usuario es un **Royal Enfield Interceptor 650 (2019)** importado de USA **sin tablero/cuadro de instrumentos**. El proyecto es construir un **TABLERO VIRTUAL** que reemplace al físico:

- Velocidad, RPM, marcha actual
- Temperatura de aceite con alertas
- Voltaje del sistema (¿alternador cargando bien?)
- Throttle, MAP, IAT, engine load
- Consumo estimado de combustible
- Alertas activas (EOT crítica, redline, voltaje raro)

**Roadmap final:** app móvil (probablemente PWA o React Native) montable en el manubrio. Mientras tanto se desarrolla con web stack en laptop.

---

## ✅ Status actual

| Componente | Estado |
|---|---|
| Hardware moto | ✓ Cable adaptador reparado y validado eléctricamente |
| Comunicación con ECU | ✓ OBD2 estándar via CAN 11-bit/500k confirmado |
| PIDs soportados | ✓ 19 PIDs identificados (RPM, speed, TPS, MAP, IAT, EOT, etc.) |
| Setup de red dual | ✓ USB WiFi adapter al dongle + integrada a internet (simultáneo) |
| Backend FastAPI | ✓ Polling continuo, JSON API, autoreconnect, logs CSV |
| Frontend Vue 3 + Vite | ✓ Dashboard funcional con velocímetro, tacómetro, gear, alertas |
| Dataset captura | ✓ 900 samples (3 min) en `mock_data/` |
| Replay server | ⏳ Pendiente — próximo paso |
| App móvil | ⏳ Pendiente — futuro próximo |

---

## 🏍️ Hardware

### Moto
- **Royal Enfield Interceptor 650**, modelo 2019
- ECU: **Bosch Motronic ME17.9.71** (P/N `0261 S18 895`, fab 31-ene-2019, Made in India)
- ABS: **Bosch 9.1M** dual channel
- Conector diagnóstico: Sumitomo MT 6-pin debajo del asiento
- **Importada de USA, sin tablero/instrument cluster**
- Manual de servicio oficial 198 pp en `interceptor_650_2018.pdf`

### Dongle de diagnóstico
- **Steren SCAN-030** = ELM327 v1.5 clone WiFi
- Crea AP propio: SSID `Steren SCAN-030`, abierto (sin password)
- IP: `192.168.0.10:35000`
- Protocolo: TCP plano, comandos AT/OBD ASCII terminados en `\r`, prompt `>`

### Adaptador USB WiFi (para setup dev en escritorio)
- Detectado como `<wlan-usb-iface>` en NetworkManager (nombre incluye la MAC del adaptador)
- Permite conectar al dongle SIN perder internet de la WiFi normal
- Configuración: ver sección "Setup de red dual" abajo

---

## 📍 Pinout del conector de la moto (CONFIRMADO con multímetro)

```
[1: +12V CONSTANTE  Rojo]  [2: CAN-H  Rojo]   [3: +12V SWITCHED  Cafe]
[4: GND            Negro]  [5: CAN-L  Azul]   [6: VACÍO              ]
```

**Pin 3 (Cafe / +12V switched):** intencionalmente NO conectado en el cable adaptador (no se usa para diagnóstico).

**La moto NO tiene K-line** — solo CAN. Por eso descartamos todos los protocolos K-line (ATSP3/4/5).

---

## 🔌 Cable adaptador (REPARADO)

Originalmente venía mal armado de fábrica + tenía un cable interno desconectado. El usuario rompió la carcasa OBD2 moldeada, identificó cables internos por continuidad, y re-soldó al pinout correcto.

**Mapeo final validado eléctricamente:**

| Sumitomo (moto) | Cable interno | OBD2 pin | Validación |
|---|---|---|---|
| 1 (+12V const Rojo) | rojo | **16** | ~12V ✅ |
| 2 (CAN-H Rojo) | blanco | **6** | ~2.7V idle ✅ |
| 3 (+12V switched Cafe) | amarillo | **NO conectado** | aislado ✅ |
| 4 (GND Negro) | negro | **4** + puente al **5** | 0V ✅ |
| 5 (CAN-L Azul) | azul | **14** | ~2.6V idle ✅ |

---

## 📡 Comunicación con la ECU — CONFIRMADA

### Protocolo
- **ISO 15765-4 CAN 11-bit / 500 kbps**
- ECU CAN ID request: `7E0`
- ECU CAN ID response: `7E8` (estándar OBD2 — no necesita CAN IDs propietarios Bosch)
- Auto-detect del ELM327 funciona (`ATSP0`)

### PIDs soportados (19 total)

```
Bitmaps obtenidos:
  0100 → B7BEC011 (16 PIDs en rango 01-20)
  0120 → 80000001 (2 PIDs en rango 21-40)
  0140 → 00000010 (1 PID en rango 41-60)
  0160 → no soportado (no hay rango 61-80)
```

| PID | Descripción | Para qué |
|---|---|---|
| `01` | Monitor status DTCs | Sistema de errores |
| `03` | Fuel system status | |
| `04` | Engine load (calculated) (%) | ⭐ Tablero |
| `06`-`09` | Fuel trims (Bank 1/2 short/long term) | |
| `0B` | MAP — Manifold absolute pressure (kPa) | ⭐ Tablero + cálculo fuel |
| `0C` | **RPM** | ⭐⭐⭐ Tablero crítico |
| `0D` | **Vehicle speed (km/h)** | ⭐⭐⭐ Tablero crítico |
| `0E` | Timing advance (°) | |
| `0F` | IAT — Intake air temp (°C) | ⭐ Tablero + cálculo fuel |
| `11` | **TPS — Throttle position (%)** | ⭐⭐ Tablero |
| `12` | Commanded secondary air status | |
| `1C` | OBD standards conformance | |
| `21` | Distance with MIL on (km) | Diagnóstico |
| `5C` | **EOT — Engine oil temperature (°C)** | ⭐⭐⭐ Tablero crítico (no hay coolant: motor air-cooled) |

### PIDs NO soportados que querríamos
- ❌ `5E` — Engine fuel rate (consumo directo). Lo calculamos con speed-density.
- ❌ `2F` — Fuel tank level (sensor de combustible va directo al tablero, no por ECU)
- ❌ `42` — Control module voltage. Usamos `ATRV` del ELM como fallback.
- ❌ PIDs O2/lambda (la ECU tiene HEGO físicamente pero no expone vía OBD2 estándar)

---

## 🌐 Setup de red dual (laptop con dos WiFi simultáneos)

Permite tener internet (para chatear/devops) Y acceso al dongle al mismo tiempo.

```
[Laptop]
    ├── wlp3s0 (WiFi interno) → "<your-home-wifi>" (192.168.1.x) → internet
    └── <wlan-usb-iface> (USB) → "Steren SCAN-030" (192.168.0.x) → dongle ELM327
```

### Setup (NetworkManager)
```bash
# Conectar el USB adapter al dongle
nmcli device wifi connect "Steren SCAN-030" ifname <wlan-usb-iface>

# Configurar para que NO sea default route (evita robar internet)
nmcli connection modify "Steren SCAN-030 1" ipv4.never-default yes ipv4.route-metric 50000

# Verificar
ip route   # default debe estar en wlp3s0 con metric bajo
```

**Caveat aprendido:** NetworkManager auto-renombra la conexión a `"Steren SCAN-030 1"` si reconecta. Usar nombre exacto para `connection modify`.

---

## 📁 Estructura del código

```
RoyalEnfieldObd/
├── backend/                    # FastAPI server
│   ├── main.py                 # endpoints + lifespan + polling thread
│   ├── obd.py                  # cliente ELM327 + decoders + cálculos
│   └── requirements.txt        # fastapi, uvicorn
│
├── frontend/                   # Vue 3 + Vite
│   ├── package.json            # vue 3.5, vite 8.0
│   ├── vite.config.js          # proxy /api → 127.0.0.1:8000
│   ├── index.html
│   └── src/
│       ├── main.js
│       ├── style.css           # tema oscuro automotriz
│       ├── App.vue             # layout grid 3 columnas
│       ├── composables/
│       │   └── useObdData.js   # polling reactivo /api/data + /api/session
│       └── components/
│           ├── Speedometer.vue       # velocímetro grande con bar
│           ├── Tachometer.vue        # tacómetro con zonas verde/amarillo/rojo
│           ├── GearDisplay.vue       # número de marcha grande
│           ├── TempGauge.vue         # gauge genérico de temperatura
│           ├── VoltageIndicator.vue  # voltaje con interpretación
│           ├── AlertsPanel.vue       # alertas activas
│           └── SessionStats.vue      # vmax, rpmmax, eot max, fuel total + reset
│
├── tools/
│   └── capture.py              # captura JSONL del backend para datasets de dev
│
├── mock_data/                  # datasets capturados para dev offline
│   └── session_20260426_175705.jsonl  # 900 samples / 3 min / 276 KB
│
├── logs/                       # CSV auto-logueados por el backend en cada arranque
│   └── ride_*.csv
│
├── # Scripts standalone (legacy útil para diagnóstico)
├── elm327_diag.py              # diagnóstico inicial / sweep de protocolos
├── elm327_pids.py              # listado de PIDs soportados
├── elm327_live.py              # live data terminal-only (sin servidor)
├── tablero.py                  # tablero ANSI terminal (predecesor del web stack)
│
├── # Documentación
├── ESTADO_PROYECTO.md          # este archivo
├── CONTEXT.md                  # contexto inicial (sesión Claude chat)
├── CONTEXT_2.md                # contexto con cable reparado
├── interceptor_650_2018.pdf    # manual oficial 198 pp
└── foto-conector-moto.jpg      # foto del Sumitomo de la moto
```

---

## 🔧 Backend — `backend/main.py`

### Arquitectura
- Thread de fondo permanente que poll-ea el dongle con backoff exponencial al reconectar
- Estado compartido protegido por `threading.Lock`
- Datos derivados (consumo de fuel, marcha estimada) recalculados después de cada PID
- Auto-loguea CSV por sesión en `logs/ride_<timestamp>.csv`

### Endpoints
- `GET /api/health` — `connected` derivado de freshness, `stale_seconds`, `last_update`
- `GET /api/data` — snapshot completo del estado actual (todos los PIDs + derivados)
- `GET /api/session` — Vmax, RPMmax, EOTmax, duración, fuel acumulado
- `POST /api/session/reset` — resetea contadores de sesión
- `GET /` — sirve frontend buildeado en producción (si existe `frontend/dist/`)

### Configurables vía env
- `VE` — volumetric efficiency para cálculo de fuel (default 0.85)
- `POLL_INTERVAL` — pausa entre ciclos (default 0.5s)
- `LOG_DIR` — carpeta de logs CSV (default `../logs`)

### Decisiones de diseño
- **State update por-PID:** después de cada query individual, no al final del ciclo (RPM aparece en pantalla en ~150ms en vez de ~700ms)
- **Connection freshness:** `connected=true` solo si `last_update` < 2s (detecta drops antes que el TCP timeout)
- **Drain del socket** antes de cada `_send()` (previene buffer cross-talk entre queries)
- **Validación estricta de ATRV:** rechaza valores fuera de 0-30V (evita el bug histórico "voltaje 410437V" causado por bytes de queries previas)

### Comandos
```bash
# Dev
cd backend && source ../venv/bin/activate
uvicorn main:app --reload --port 8000

# Prod (sirviendo el dist/ del frontend)
cd backend && uvicorn main:app --port 8000
```

---

## 🎨 Frontend — Vue 3 + Vite

### Características
- Dashboard responsive (3 columnas en desktop, 1 en celular)
- Tema oscuro estilo automotriz (paleta GitHub-dark variants)
- Update reactivo cada 500ms via `useObdData` composable
- **Estado "stale":** cuando el backend reporta no-conectado, el contenido se atenúa (opacity 0.4 + grayscale) — el header sigue claro mostrando "Sin datos hace Ns"
- Indicador de conexión en el header (verde/amarillo/rojo)
- Botón de reset de sesión

### Componentes
- **Speedometer** — número grande km/h, barra horizontal, cambio de color a >80 (warn) >100 (danger)
- **Tachometer** — número RPM, barra con zonas verde (<5000) / amarillo (<6000) / rojo (>=6000), redline a 7400
- **GearDisplay** — número grande de marcha, "N" para neutral, "—" para parado
- **TempGauge** — genérico (usado para EOT y IAT) con etiquetas dinámicas Frío/Normal/Alto/DETENER
- **VoltageIndicator** — interpretación textual: "Cargando OK" / "Bajo" / "Regulador?"
- **AlertsPanel** — alertas críticas con animación de pulso
- **SessionStats** — Vmax, RPMmax, EOTmax, duración, combustible acumulado

### Comandos
```bash
cd frontend
npm run dev      # dev server con HMR en :5173
npm run build    # genera dist/ para producción
```

### Vite proxy (importante)
```js
// vite.config.js
server: {
  host: '127.0.0.1',
  proxy: {
    '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true }
  }
}
```
**Por qué `127.0.0.1` y no `localhost`:** cuando estás conectado a la WiFi del dongle (que no tiene DNS), Node.js falla con `ENOTFOUND localhost`. IP directa evita el lookup.

---

## 📊 Cálculos derivados

### Marcha estimada (gear)
Usando ratios documentados en manual p.4:
- Primary ratio: 2.05:1
- Secondary ratio: 2.533:1
- Gears: 1ª=2.615, 2ª=1.813, 3ª=1.429, 4ª=1.190, 5ª=1.040, 6ª=0.962
- Tire trasera 130/70 R18 → circumferencia ~2.008 m

```
ratio_efectivo = RPM / wheel_RPM / (primary × secondary)
gear = la del manual cuyo ratio es más cercano (tolerancia 15%)
```

Funciona muy bien en práctica — testeado contra todas las marchas en captura.

### Consumo de combustible (speed-density)
```
MAF (g/s) = MAP_kPa × Disp_L × RPM × VE × M_air / (R × IAT_K × 120)
fuel_gs = MAF / 14.7  (AFR estequiométrico)
fuel_L/h = fuel_gs × 3600 / 745.7  (densidad gasolina)
```

**Limitación conocida:** sobreestima a bajo RPM (idle reportó 1.4 L/h vs ~0.4 L/h real esperado). Causa: VE asumido constante 0.85 pero en realidad VE varía con RPM (idle ~0.35, 3000-5500 RPM ~0.85, redline ~0.75). Mejora futura: tabla 2D MAP×RPM → VE con calibración empírica.

---

## 📦 Dataset capturado para development offline

**Archivo:** `mock_data/session_20260426_175705.jsonl`

- 900 samples
- 180 segundos
- 5 Hz (sample cada 200ms)
- 276 KB
- 0 errores

### Cobertura del dataset
```
RPM:     1078 - 4275 (avg 1463)        76% en 1000-1500 (idle)
Speed:   0 - 52 km/h (avg 8)
TPS:     13.7% - 18.8% (avg 14.1%)     85% en 0-15% (idle), 15% en 15-25%
MAP:     27 - 66 kPa (avg 46)
IAT:     7 - 9°C (mañana fresca Guate)
EOT:     82 - 92°C (operativa real, finalmente warm-up completo)
Load:    9.8% - 54.9% (avg 19.3%)
Voltage: 13.3 - 14.2V (avg 13.8 — alternador OK)
Fuel:    0.7 - 5.2 L/h (avg 1.3, sobreestimado a idle)

Marchas detectadas:
  1ª: 14% (126 samples)
  2ª: 0.1% (1 sample)
  3ª: 0.6%
  4ª: 0.6%
  5ª: 4.6%
  6ª: 11.9%
  Neutral/parado: 68.3%
```

### Limitaciones del dataset
- ⚠️ TPS no pasó del 18.8% (no se hizo throttle agresivo, moto en caballete)
- ⚠️ RPM tope 4275 (no hay datos de 5000-7400 RPM ni redline)
- ⚠️ Marchas 2/3/4 muy poco representadas
- ✅ Cold-to-warm cycle EOT 49→92°C presente
- ✅ Cambios de gear limpios, gear detection funciona perfecto

**Implicación:** suficiente para desarrollar el dashboard end-to-end. Para casos extremos (alertas críticas, animaciones de redline) considerar:
- Segunda captura en ruta real (no caballete)
- O generador sintético de datos extremos

---

## 🛠️ Tools

### `tools/capture.py`
Polea `/api/data` a tasa configurable, guarda JSONL.
```bash
python3 tools/capture.py                    # 180s a 5 Hz
python3 tools/capture.py --duration 300     # 5 min
python3 tools/capture.py --rate 10          # 10 Hz
python3 tools/capture.py --out custom.jsonl
```

### `tools/replay_server.py` ⏳ PENDIENTE
Mock FastAPI que sirve los mismos endpoints (`/api/data`, `/api/session`, `/api/health`) leyendo un JSONL y reproduciéndolo en loop. Reemplaza al backend real cuando no estás cerca de la moto.

---

## 🐛 Bugs históricos resueltos (para no repetir)

1. **Auto-detect false positive** (script v1): la lógica `is_bad()` no detectaba `"SEARCHING..."` como respuesta inválida → falso "OK". Fix: lista de palabras clave incluye SEARCHING/UNABLE/etc.

2. **K-line BUS INIT...ERROR** (sesión inicial): pensábamos que era address propietario; en realidad la moto NO tiene K-line, solo CAN. Pin 3 marrón es +12V switched, no K-line.

3. **Cable wrong pinout** (Steren venía mal de fábrica): K-line al pin 16 OBD2 (debería ser 7), +12V al pin 14 (debería ser 16), CAN-L sin mapear. Resuelto rompiendo carcasa OBD2 y re-soldando.

4. **Voltaje 410437.0V** (bug clásico de buffer): respuestas viejas de queries OBD se quedaban en buffer del socket; cuando se mandaba ATRV, leía esos bytes (`410437` = `41 04 37` = respuesta a Mode 01 PID 04). Fix: drenar buffer antes de cada `_send()` + validar formato ATRV (debe terminar en V, valor 0-30).

5. **"Conectado" mentiroso** (UI): cuando el dongle se desconectaba el indicador tardaba 5-10s en cambiar (timeout TCP). Fix: derivar `connected` de freshness del `last_update`, no del estado del socket.

6. **`ENOTFOUND localhost`** (Vite proxy): Node 17+ resuelve localhost por DNS, falla cuando WiFi del dongle no tiene DNS. Fix: usar `127.0.0.1` directamente en el proxy.

7. **NM connection name mismatch**: NetworkManager auto-renombra a `"Steren SCAN-030 1"` (con sufijo "1") al reconectar. `nmcli connection modify` necesita el nombre exacto.

8. **NM `up`/`down` rompió default route**: hacer `down` + `up` para aplicar `never-default` puede dejar wlp3s0 sin default route. Fix preferido: `nmcli connection modify` con `route-metric 50000` (no requiere reactivar).

---

## 📝 Próximos pasos

### Inmediato (próxima sesión)
- [ ] **`tools/replay_server.py`** — mock backend que reproduce el JSONL capturado, mismos endpoints. Permite desarrollar frontend SIN moto.

### Corto plazo
- [ ] Segunda captura en ruta real (cuando manejen) — para tener datos de RPM altos / throttle agresivo / redline. Opcional pero útil.
- [ ] **Generador sintético** — script que produce eventos artificiales (ramp-up de RPM, alertas, decel cuts) para testing UI de casos extremos.
- [ ] Calibrar VE empíricamente: llenar tanque, andar X km, restar litros usados, ajustar VE para que matche.

### Mediano plazo
- [ ] **Build de producción** — `npm run build` + servir `dist/` desde FastAPI directamente (puerto único 8000)
- [ ] Persistir sesiones en SQLite para histórico de viajes
- [ ] Logging de DTCs (Mode 03) además de live data
- [ ] Borrar DTCs (Mode 04) desde la UI

### Largo plazo
- [ ] **App móvil** — PWA o React Native consumiendo la misma API. Montable en manubrio.
- [ ] Raspberry Pi como host permanente (en la moto, alimentado por +12V switched)
- [ ] Notificaciones (Telegram/email/sonido) para alertas críticas
- [ ] Sweep Mode 22 / UDS para PIDs propietarios Bosch (consumo real, fuel level si está expuesto vía DID raro)

---

## 🧠 Aprendizajes clave

1. **El protocolo OBD2 estándar SÍ funciona** en la Bosch ME17.9.71 — no necesita CAN IDs propietarios. Esto fue una sorpresa positiva. La pista la dio el manual: los DTCs vienen en formato P-código estándar.

2. **El cable adaptador genérico estaba MAL** — pero el diagnóstico (multímetro + comparar contra estándar OBD2 J1962) fue lo que destrabó todo. Sin ese debug detallado del pinout, hubiéramos seguido culpando al protocolo o al dongle.

3. **El ELM327 v1.5 clone es razonablemente confiable** — algunos hiccups (drops cada tanto, buffer cross-talk si no se drena) pero funcional para producción casera.

4. **El setup dual WiFi (USB adapter + integrada) es game-changer para dev** — permite tener Claude y la moto al mismo tiempo. NetworkManager lo soporta nativamente con `never-default yes` + `route-metric` alto.

5. **State update por-PID en vez de batch** mejoró latencia 5x sin cambiar nada físico. Las decisiones de granularidad de update importan más que el throughput bruto.

6. **El dataset capturado es oro** para desarrollo offline. 3 minutos de actividad variada → suficiente para iterar el frontend semanas sin tocar la moto.

---

## 👤 Preferencias del usuario

- **David**, Fedora Linux + macOS, fluido en terminal
- Hardware tinkerer (treadmills, OBD2, MDB protocol)
- Stack preferido: **Python para scripting, FastAPI + Vue/Astro para web**
- Prefiere **explicaciones detalladas** (lleva registro)
- Verificar specs de hardware antes de "corregirlas" — confiar en manual oficial sobre memoria
- **Mockoso/práctico:** prefiere ver respuestas crudas, capturar datos reales, no abstracciones
