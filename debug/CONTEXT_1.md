# Contexto: Diagnóstico OBD para Royal Enfield Interceptor 650 (2019)

## Resumen del proyecto

El usuario quiere leer el puerto de diagnóstico de su **Royal Enfield Interceptor 650 modelo 2019** desde su laptop Linux, vía un dongle ELM327 WiFi. La meta inmediata es **diagnosticar si la moto responde a comandos OBD2 estándar**, y según el resultado, decidir si vale la pena seguir por ese camino o si hay que cambiar de hardware/software.

## Hardware involucrado

### Moto
- **Royal Enfield Interceptor 650**, modelo 2019
- ECU: **Bosch ME17.9.x** (común en RE 650 Twin)
- Confirmado por el manual de servicio oficial 2018 (198 páginas) que la moto:
  - **NO usa el conector OBD2 SAE J1962 estándar de 16 pines**
  - Usa un conector propietario tipo **Sumitomo de 6 vías** (3×2)
  - Tiene comunicación CAN bus interna (códigos U0009, U0121, U0415 documentados)
  - Oficialmente solo se diagnostica con la **ICM Diagnostic Tool** de Royal Enfield (software *Royal ABS 9.1 M / Bosch ABS system*)
  - El manual de servicio NO documenta el pinout del conector de 6 vías

### Conector de la moto (lado del cableado/arnés)
- 6 cavidades en configuración 3×2
- 5 cavidades ocupadas, 1 sellada con tapón ciego
- Cables visibles aproximadamente:
  - Fila superior: gris, rojo, marrón
  - Fila inferior: rojo, rojo, [vacío]
- Es típico que estos conectores lleven: +12V switched, GND, K-line, CAN-H, CAN-L

### Cable adaptador
- El usuario compró un cable adaptador: conector hembra Sumitomo 6 vías → OBD2 hembra J1962 16 pines
- Físicamente encaja en la moto. **No está validado eléctricamente** (no se ha medido si el pinout interno es correcto).

### Dongle escáner
- **Steren SCAN-030**
- Etiqueta: "Escáner automotriz, Alimentación: 12V, Frecuencia: 2.4 GHz, PO# 320108, Hecho en China"
- Es un **ELM327 genérico** con conexión inalámbrica (WiFi, según se confirmó por la app)
- Crea un Access Point WiFi propio cuando se alimenta

### App móvil que está usando
- **EOBD-Facile / klavkarr** versión 3.84 (Outils OBD Facile SAS)
- Configurada como ELM327 Wi-Fi
- IP: `192.168.0.10`
- Puerto: `35000`
- La app **no detecta señal del vehículo**, aunque el dongle aparentemente sí se conecta

## Estado actual del problema

El usuario conecta el dongle a la moto vía el cable adaptador, prende la moto en KEY ON, abre la app, y **la app no logra leer ninguna señal del vehículo**.

Esto puede tener varias causas (hipótesis ordenadas por probabilidad):

1. **La ECU Bosch ME17 del Interceptor no responde a OBD2 estándar SAE J1979** — solo responde a comandos KWP2000/UDS específicos de Royal Enfield. Esta es la hipótesis principal según la documentación del manual de servicio.
2. **El cable adaptador tiene el pinout mal mapeado** entre los 6 pines de la moto y los 16 pines del OBD2. Sin documentación oficial del pinout de RE, los fabricantes de cables genéricos a veces se equivocan.
3. **El dongle no está bien alimentado** (el pin 16 +12V del OBD2 no está bien conectado en el cable adaptador).
4. **La app está intentando solo PIDs estándar OBD2** y no comandos propietarios.

## Plan de diagnóstico

Como el dongle ELM327 es básicamente un **socket TCP en `192.168.0.10:35000`** que recibe comandos AT/OBD en texto plano, se decidió **saltarse la app móvil** y conectarse directamente desde la laptop Linux para tener control total.

El plan tiene los siguientes pasos en orden:

1. **Verificar conexión TCP** al dongle desde la laptop
2. **Handshake ELM327** (`ATZ`, `ATI`) — si esto no responde, el problema es de red/dongle, no de moto
3. **Verificar voltaje** (`ATRV`) — si da 0V o muy bajo, el cable adaptador tiene mal el pin +12V
4. **Auto-detect protocolo** (`ATSP0` + query `0100`)
5. **Si auto-detect falla**, forzar manualmente cada protocolo del 3 al 9:
   - `ATSP3` → ISO 9141-2 (K-line)
   - `ATSP4` → ISO 14230-4 KWP slow init
   - `ATSP5` → ISO 14230-4 KWP fast init (más probable para Bosch ME17)
   - `ATSP6` → ISO 15765-4 CAN 11-bit/500k
   - `ATSP7` → ISO 15765-4 CAN 29-bit/500k
   - `ATSP8` → ISO 15765-4 CAN 11-bit/250k
   - `ATSP9` → ISO 15765-4 CAN 29-bit/250k

## Script de diagnóstico ya creado

Se creó `elm327_diag.py` que automatiza todo el plan anterior usando solo `socket` de stdlib (sin dependencias externas).

Comportamiento esperado del script:

```
python3 elm327_diag.py
```

Tres escenarios de salida posibles:

| Resultado | Significado | Próximo paso |
|---|---|---|
| Falla en conexión TCP | WiFi mal o dongle sin alimentar | Revisar red WiFi y cable |
| `ATRV` da 0V | Cable adaptador mal armado en pin 16 | Revisar continuidad del cable |
| Algún protocolo responde a `0100` | La moto SÍ habla OBD2 estándar | Implementar lector de DTCs |
| Ningún protocolo responde | ECU propietaria confirmada | Buscar hardware específico de RE |

## Caminos posibles según resultado

### Si el script confirma que SÍ responde algún protocolo OBD2

- Extender el script para leer DTCs (Mode 03), borrar DTCs (Mode 04), live data (Mode 01), etc.
- Implementar un dashboard simple en consola (curses) o web (Flask local) que muestre RPM, throttle, coolant temp, etc.

### Si el script confirma que NO responde a ningún protocolo OBD2 estándar

- La moto usa KWP2000/UDS propietario de Bosch. Opciones:
  1. **HealTech OBD Tool** con perfil para Royal Enfield 650 Twin (~USD $100)
  2. **Power Tronic ECU** con su Bluetooth dongle (más caro, además permite remapear)
  3. **Investigación del protocolo Bosch propietario** vía sniffing del CAN bus con un adaptador SocketCAN (más DIY, más en el estilo del usuario)
  4. **Construir un cable adaptador desde cero** después de mapear los pines con un multímetro, e investigar si los CAN-H/CAN-L del conector se pueden leer con un dongle SocketCAN apropiado (más nivel hacker)

## Información técnica adicional sobre el ELM327 vía WiFi

- Protocolo: TCP plano (no HTTP, no MQTT, nada raro)
- Endpoint: `192.168.0.10:35000` (típico, configurable en algunos clones)
- Formato de comandos: ASCII terminados en `\r` (CR, no CRLF)
- Formato de respuestas: ASCII, líneas separadas por `\r`, terminadas con prompt `>`
- Comandos AT controlan el adaptador (`ATZ`, `ATSP`, `ATRV`, `ATE0`, etc.)
- Comandos hex (`0100`, `03`, `0902`, etc.) son los Mode/PID de OBD2 que se mandan al vehículo
- El ELM327 hace de traductor entre TCP-ASCII y el protocolo físico del vehículo (K-line, CAN, etc.)

## Preferencias del usuario

- Trabaja en Linux (Fedora) y macOS, comfortable con terminal
- Prefiere explicaciones detalladas para llevar registro
- Disfruta hardware tinkering (modifica treadmills, trabaja con OBD2, MDB protocol, etc.)
- Prefiere stack: Python para scripting, Astro + FastAPI para web
- Usa Claude Code en su laptop Linux para desarrollo

## Estado de archivos

- `elm327_diag.py` — script base de diagnóstico ya creado, sin dependencias externas, funcional pero sin probar todavía contra la moto real
- El usuario aún no ha corrido el script, está en proceso de configurar el entorno

## Lo que se NECESITA hacer ahora

1. Validar que el script corra correctamente (sintaxis ya validada)
2. Que el usuario lo ejecute conectado al WiFi del dongle con la moto en KEY ON
3. Interpretar los resultados juntos
4. Según el resultado, decidir el siguiente paso (extender el script o cambiar de hardware)

## Lo que NO se debe hacer

- No asumir que la moto es OBD2 compliant solo porque el conector OBD2 físicamente encaja
- No recomendar comprar nuevo hardware ANTES de ejecutar el script de diagnóstico — primero datos, luego decisiones
- No usar librerías externas (python-OBD, etc.) en esta etapa — el objetivo es ver respuestas crudas para diagnosticar, no abstraer encima del problema
- No confiar ciegamente en lo que la app móvil reporta — puede estar filtrando o malinterpretando respuestas
