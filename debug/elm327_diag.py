#!/usr/bin/env python3
"""
Diagnóstico OBD/ELM327 vía WiFi para Royal Enfield Interceptor 650.

Uso:
    1. Conectar la moto: llave en KEY ON
    2. Conectar la laptop al WiFi del dongle ELM327 (red "WiFi_OBDII" o similar)
    3. python3 elm327_diag.py

Lo que hace:
    - Verifica conexión TCP al dongle (192.168.0.10:35000)
    - Hace handshake con el ELM327 y muestra la versión del firmware
    - Lee voltaje de batería (confirma que el cable adaptador alimenta bien)
    - Prueba auto-detección de protocolo OBD2
    - Si auto-detect falla, fuerza cada protocolo (3 al 9) y prueba responder
    - Imprime un resumen claro de qué protocolo (si alguno) responde
"""

import socket
import time
import sys

HOST = "192.168.0.10"
PORT = 35000
TIMEOUT = 5.0  # segundos por comando


def send_cmd(sock: socket.socket, cmd: str, wait: float = 0.3) -> str:
    """Envía un comando AT/OBD y devuelve la respuesta limpia."""
    sock.sendall((cmd + "\r").encode("ascii"))
    time.sleep(wait)
    buf = b""
    sock.settimeout(TIMEOUT)
    try:
        while True:
            chunk = sock.recv(1024)
            if not chunk:
                break
            buf += chunk
            # El ELM327 termina cada respuesta con el prompt '>'
            if b">" in buf:
                break
    except socket.timeout:
        pass
    # Limpia: quita el eco del comando, el prompt, espacios y \r
    text = buf.decode("ascii", errors="replace")
    text = text.replace(cmd, "").replace(">", "").replace("\r", "\n")
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


BAD_RESPONSES = (
    "NO DATA", "UNABLE", "ERROR", "?", "STOPPED",
    "CAN ERROR", "BUS INIT", "SEARCHING", "BUS BUSY", "DATA ERROR",
)


def is_bad(resp: str) -> bool:
    """Devuelve True si la respuesta indica fallo o está incompleta."""
    if not resp:
        return True
    return any(b in resp.upper() for b in BAD_RESPONSES)


def test_protocol(sock: socket.socket, num: int, name: str) -> bool:
    """Fuerza un protocolo y prueba un PID estándar. Devuelve True si responde algo útil."""
    print(f"\n--- Protocolo {num}: {name} ---")
    # Cerrar protocolo anterior antes de cambiar (evita estado sucio)
    send_cmd(sock, "ATPC")
    print(f"  ATSP{num}: {send_cmd(sock, f'ATSP{num}')}")
    # KWP slow init puede tardar hasta 5s; CAN ~2s; damos 6s para cubrir todo
    resp = send_cmd(sock, "0100", wait=6.0)
    print(f"  0100   : {resp}")
    # ATDP es la autoridad final del ELM sobre qué pasó
    dp = send_cmd(sock, "ATDP")
    print(f"  ATDP   : {dp}")
    return not is_bad(resp) and not is_bad(dp)


def main() -> int:
    print(f"Conectando a ELM327 en {HOST}:{PORT}...")
    try:
        sock = socket.create_connection((HOST, PORT), timeout=TIMEOUT)
    except (socket.timeout, ConnectionRefusedError, OSError) as e:
        print(f"ERROR: no pude conectar al dongle ({e})")
        print("Verificá:")
        print("  - WiFi de la laptop conectado a la red del dongle")
        print("  - Llave de la moto en KEY ON")
        print("  - Dongle bien insertado en el adaptador OBD2")
        return 1

    print("Conexión TCP OK.\n")

    # 1. Handshake básico - confirma que el dongle responde
    print("=== Handshake ELM327 ===")
    print(f"ATZ (reset)     : {send_cmd(sock, 'ATZ', wait=1.5)}")
    print(f"ATE0 (no echo)  : {send_cmd(sock, 'ATE0')}")
    print(f"ATL0 (no LF)    : {send_cmd(sock, 'ATL0')}")
    print(f"ATH1 (headers)  : {send_cmd(sock, 'ATH1')}")
    print(f"ATS0 (no spaces): {send_cmd(sock, 'ATS0')}")
    print(f"ATI (versión)   : {send_cmd(sock, 'ATI')}")

    # 2. Voltaje - confirma que el cable adaptador entrega +12V
    voltage = send_cmd(sock, "ATRV")
    print(f"ATRV (voltaje)  : {voltage}")
    if voltage and "0.0" in voltage:
        print("  ⚠️  Voltaje muy bajo: revisá el pin +12V del cable adaptador.")
    elif voltage:
        print("  ✓ Cable adaptador alimentando correctamente.")

    # 3. Auto-detect de protocolo
    print("\n=== Auto-detect (ATSP0) ===")
    print(f"ATSP0           : {send_cmd(sock, 'ATSP0')}")
    # Auto-detect puede pasear por todos los protocolos: damos 8s
    auto_resp = send_cmd(sock, "0100", wait=8.0)
    print(f"0100            : {auto_resp}")
    auto_dp = send_cmd(sock, "ATDP")
    print(f"ATDP            : {auto_dp}")

    if not is_bad(auto_resp) and not is_bad(auto_dp):
        print(f"\n✅ La moto respondió OBD2 estándar. Protocolo: {auto_dp}")
        sock.close()
        return 0

    # 4. Si auto-detect falla, forzar cada protocolo manualmente
    print("\n=== Auto-detect falló. Probando protocolos forzados ===")
    protocols = {
        3: "ISO 9141-2 (K-line)",
        4: "ISO 14230-4 KWP slow init",
        5: "ISO 14230-4 KWP fast init",  # más probable para Bosch ME17
        6: "ISO 15765-4 CAN 11-bit/500k",
        7: "ISO 15765-4 CAN 29-bit/500k",
        8: "ISO 15765-4 CAN 11-bit/250k",
        9: "ISO 15765-4 CAN 29-bit/250k",
    }
    matches = [num for num, name in protocols.items() if test_protocol(sock, num, name)]

    print("\n" + "=" * 50)
    if matches:
        print(f"✅ Protocolos que respondieron: {matches}")
        print("La moto SÍ habla OBD2 estándar en al menos uno de estos.")
    else:
        print("❌ Ningún protocolo OBD2 estándar respondió.")
        print("Confirma que el Interceptor 650 NO es OBD2 compliant.")
        print("Necesitás hardware/software específico de Royal Enfield.")
    print("=" * 50)

    sock.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
