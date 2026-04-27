# Contexto: Diagnóstico OBD para Royal Enfield Interceptor 650 (2019)

## Resumen del proyecto

El usuario quiere leer el puerto de diagnóstico de su **Royal Enfield Interceptor 650 modelo 2019** desde su laptop Linux (Fedora), vía un dongle ELM327 WiFi. La meta inmediata es **probar la conexión, identificar el protocolo correcto, y leer datos en tiempo real (RPM, temperatura, throttle, etc.)**.

## Estado actual: HARDWARE LISTO PARA PROBAR

El cable adaptador fue **reparado y validado**. Todas las mediciones eléctricas confirman que el cableado está correcto. El siguiente paso es conectar el dongle y correr el script de diagnóstico.

## Hardware

### Moto
- **Royal Enfield Interceptor 650**, modelo 2019
- **ECU confirmada**: Bosch Motronic **ME17.9.71** (P/N: `0261 S18 895`, fabricación 31-ene-2019, Made in India)
- Esta ECU es la misma que usan algunos Suzuki y Chevrolet, está soportada por TunerPro y herramientas comerciales
- Cumple Euro 4 (conector blanco/transparente)
- Ubicación de la ECU: bajo el asiento

### Conector de diagnóstico de la moto
- Sumitomo MT 6 vías hembra (3×2)
- Pinout identificado por mediciones eléctricas:

```
Vista frontal del conector de la moto:
   [1-rojo]  [2-rojo]  [3-marrón]
   [4-negro] [5-azul]  [6-vacío]

Pin 1 (rojo)   = +12V batería directo (Vbat permanente)
Pin 2 (rojo)   = CAN-H
Pin 3 (marrón) = +12V switched (ignición) - NO SE USA
Pin 4 (negro)  = GND
Pin 5 (azul)   = CAN-L
Pin 6          = sin uso (sellado)
```

### Cable adaptador (REPARADO)
Originalmente venía mal mapeado de fábrica. Tenía un cable interno desconectado (rojo) que rompía la conexión CAN-H. El usuario lo desarmó, identificó los cables internos por continuidad, y lo re-soldó manualmente.

**Mapeo actual del cable adaptador (validado eléctricamente):**

```
Pin moto              →  Cable interno   →  Pin OBD2 hembra
─────────────────────────────────────────────────────────
Pin 1 (rojo, Vbat)    →  rojo            →  Pin 16
Pin 2 (rojo, CAN-H)   →  blanco          →  Pin 6
Pin 3 (marrón)        →  amarillo        →  no conectado (aislado)
Pin 4 (negro, GND)    →  negro           →  Pin 4 (con puente al Pin 5)
Pin 5 (azul, CAN-L)   →  azul            →  Pin 14
```

**Mediciones de validación final (KEY ON, modo voltaje DC):**
- Pin 16 OBD2 = ~12V ✅ (Vbat presente)
- Pin 4 OBD2 = ~0V ✅ (GND correcto)
- Pin 6 OBD2 = ~2.7V ✅ (CAN-H idle)
- Pin 14 OBD2 = ~2.6V ✅ (CAN-L idle)

**Test de cortocircuitos (KEY OFF, modo continuidad):**
- Ningún par de pines críticos suena bip ✅ (sin cortocircuitos)
- Pin 4 ↔ Pin 5 sí suena bip ✅ (puente correcto)

### Dongle escáner
- **Steren SCAN-030**
- ELM327 genérico WiFi (frecuencia 2.4 GHz)
- Crea un Access Point WiFi propio cuando se alimenta
- Internamente tiene chip ELM327 + transceptor S1T3044 (K-line) + módulo WiFi
- IP típica: `192.168.0.10`, puerto: `35000`
- **Estado**: vivo, validado físicamente

## Protocolo confirmado

Por las mediciones eléctricas (CAN-H y CAN-L con voltajes idle típicos de CAN bus, ~2.5V) y por la documentación de la ECU Bosch ME17.9.71, el protocolo de comunicación es:

**CAN bus (no K-line)**
- Probable: ISO 15765-4 CAN 11-bit/500k → comando ELM327 `ATSP6`
- Alternativo: ISO 15765-4 CAN 29-bit/500k → comando ELM327 `ATSP7`

## Lo que se sabe sobre el ECU

Búsquedas web confirman:
- La ECU Bosch ME17.9.71 del Royal Enfield Interceptor 650 **soporta diagnóstico OBD2 vía ELM327**
- Cables comerciales (AMHTDOL en Amazon) explícitamente dicen: *"can see live diagnostic data, read and erase error codes"*
- La comunidad ha logrado leer RPM, temp, throttle, MAP, lambda, etc.
- Esta misma ECU es usada para flashear mapas con TunerPro y Power Tronic
- Modelos Euro 4 (como este 2019) usan conector blanco. Modelos Euro 5 usan rojo.

## Script de diagnóstico ya creado

Existe `elm327_diag.py` que automatiza todo el plan de diagnóstico. Sin dependencias externas (solo `socket` de stdlib). Ubicación: directorio del proyecto.

Comportamiento del script:
1. Conexión TCP a `192.168.0.10:35000`
2. Handshake con ELM327 (`ATZ`, `ATI`, `ATE0`, `ATL0`)
3. Lectura de voltaje (`ATRV`)
4. Auto-detect protocolo (`ATSP0` + `0100`)
5. Si auto-detect falla, fuerza protocolos del 3 al 9 manualmente

**Nota importante**: el script actual prueba protocolos en orden numérico (3 al 9). Como ya sabemos que es CAN bus, sería más eficiente probar `ATSP6` y `ATSP7` primero. No es bloqueante, solo optimización.

## Lo que NECESITA hacer ahora el usuario

1. **Conectar el cable adaptador a la moto, KEY ON**
2. **Conectar el dongle Steren al cable adaptador**
3. **Verificar que el LED del Steren encienda**
4. **Conectar la laptop al WiFi del dongle** (red `WiFi_OBDII` o similar, sin contraseña o `12345678`)
5. **Test rápido con netcat**:
   ```bash
   nc 192.168.0.10 35000
   ```
   Enviar `ATZ` y esperar respuesta tipo `ELM327 v1.5`
6. **Correr el script**:
   ```bash
   python3 elm327_diag.py
   ```
7. **Compartir la salida completa** para diagnóstico

## Tareas para Claude Code

### Si el script confirma comunicación CAN

Extender el script o crear nuevos para:

1. **Lector de DTCs** - leer códigos de falla (Mode 03), borrarlos (Mode 04)
2. **Live data básico** - RPM (010C), temperatura (0105), throttle (0111), MAP (010B), velocidad (010D), voltaje módulo (0142)
3. **Logger** - guardar lecturas en CSV o SQLite con timestamp para análisis posterior
4. **Dashboard simple** - opciones:
   - Terminal (curses): tachómetro y gauges en tiempo real
   - Web local: FastAPI sirviendo data, frontend Astro/React con gauges
   - Mobile-friendly: que funcione bien en celular cuando ande en la moto

### Si el script muestra que solo responde a algunos PIDs

1. Implementar **scanner de PIDs soportados** - probar PIDs uno por uno y armar lista de los que responden
2. Probar **comandos KWP2000 propietarios de Bosch** para acceder a datos no estándar

### Si el script no logra comunicación

1. Modificar para probar `ATSP6` y `ATSP7` primero (CAN bus)
2. Probar comandos AT más específicos del ELM327 para CAN
3. Considerar que la ECU puede requerir protocolo CAN extendido o velocidades no estándar

## Stack del usuario

- **OS**: Fedora Linux (también macOS)
- **Lenguajes preferidos**: Python para scripting, Astro + FastAPI para web
- **Hardware tinkering**: confortable con multímetro, soldadura, electrónica básica
- **Idiomas**: trabaja en español e inglés
- **Estilo**: prefiere explicaciones detalladas para llevar registro

## Información técnica relevante

### ELM327 vía WiFi
- Protocolo: TCP plano (no HTTP, no MQTT)
- Endpoint: `192.168.0.10:35000`
- Comandos en ASCII terminados en `\r` (CR, no CRLF)
- Respuestas en ASCII, líneas separadas por `\r`, terminadas con prompt `>`
- Comandos AT controlan el adaptador: `ATZ` (reset), `ATSP0` (auto-protocolo), `ATSP6` (CAN 11/500k), `ATRV` (voltaje), `ATE0` (no echo), `ATL0` (no linefeed), `ATI` (versión), `ATDP` (describe protocolo)
- Comandos hex (`0100`, `010C`, `03`, etc.) son las queries OBD2 reales

### PIDs útiles esperados
- `0100` - PIDs soportados (debería responder con bytes hex indicando qué PIDs están disponibles)
- `010C` - RPM del motor
- `010D` - Velocidad del vehículo
- `0105` - Temperatura del coolant
- `0111` - Posición del throttle (TPS)
- `010F` - Temperatura del aire admisión
- `010B` - Presión absoluta del manifold (MAP)
- `0104` - Carga del motor calculada
- `0142` - Voltaje del módulo de control
- `0103` - Estado del sistema de combustible
- `0114` a `011B` - Sondas lambda (O2 sensors)
- `03` - Leer DTCs almacenados
- `04` - Borrar DTCs
- `0902` - Leer VIN
- `0904` - Calibration ID

## Lo que NO hacer

- No usar `python-OBD` u otras librerías abstractoras todavía. Queremos ver respuestas crudas para diagnosticar.
- No asumir que la moto responde a todos los PIDs estándar OBD2 — algunas ECUs solo exponen un subconjunto.
- No conectar el Steren si las mediciones de voltaje no son las correctas — puede dañarlo.
- No mover los cables soldados sin necesidad — están físicamente delicados.

## Historia breve del proyecto

1. Usuario quería leer OBD de su Interceptor con dongle Steren + cable adaptador comercial → la app no detectaba nada
2. Identificamos que el cable adaptador venía **mal mapeado de fábrica** (CAN-H en pin 6, pero Vbat en pin 14 en lugar de CAN-L)
3. Además **un cable interno (rojo) estaba desconectado** internamente
4. El usuario rompió el cable adaptador para acceder a los cables internos
5. Identificamos por continuidad cuál cable interno corresponde a cuál pin OBD2
6. Re-soldamos los 5 cables al pinout correcto del OBD2
7. Validamos eléctricamente: voltajes correctos, no hay cortocircuitos, polaridad correcta
8. **Estado actual: listo para conectar el dongle y correr el script**
