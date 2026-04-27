#!/usr/bin/env python3
"""
Listado de PIDs OBD2 soportados por la ECU.

Hace auto-detect de protocolo y consulta los 4 bitmaps de PIDs soportados
(01-20, 21-40, 41-60, 61-80). Decodifica cada bitmap y muestra qué PIDs
responde la ECU, marcando los útiles para nuestro objetivo.

Uso:
    1. KEY ON, dongle conectado, laptop en WiFi del dongle
    2. python3 elm327_pids.py | tee pids_$(date +%Y%m%d_%H%M).txt
"""

import socket
import time
import sys

HOST = "192.168.0.10"
PORT = 35000
TIMEOUT = 8.0

# PIDs interesantes para nuestro objetivo (consumo, motor en vivo)
USEFUL = {0x04, 0x05, 0x0B, 0x0C, 0x0D, 0x0F, 0x11, 0x42, 0x46,
          0x5C, 0x5D, 0x5E, 0x2F, 0x33, 0x21, 0x1F}

# Diccionario de PIDs OBD2 estándar (Mode 01) — los más comunes
PID_NAMES = {
    0x01: "Monitor status since DTCs cleared",
    0x02: "Freeze DTC",
    0x03: "Fuel system status",
    0x04: "Calculated engine load (%)",
    0x05: "Engine coolant temperature (°C)",
    0x06: "Short term fuel trim Bank 1 (%)",
    0x07: "Long term fuel trim Bank 1 (%)",
    0x08: "Short term fuel trim Bank 2 (%)",
    0x09: "Long term fuel trim Bank 2 (%)",
    0x0A: "Fuel pressure (kPa)",
    0x0B: "Intake manifold abs. pressure / MAP (kPa)",
    0x0C: "Engine RPM",
    0x0D: "Vehicle speed (km/h)",
    0x0E: "Timing advance (°)",
    0x0F: "Intake air temperature / IAT (°C)",
    0x10: "MAF air flow rate (g/s)",
    0x11: "Throttle position / TPS (%)",
    0x12: "Commanded secondary air status",
    0x13: "Oxygen sensors present (2-bank)",
    0x14: "O2 Sensor 1 voltage + STFT",
    0x15: "O2 Sensor 2 voltage + STFT",
    0x1C: "OBD standards conformance",
    0x1D: "Oxygen sensors present (4-bank)",
    0x1E: "Auxiliary input status",
    0x1F: "Run time since engine start (s)",
    0x20: "PIDs supported [21-40]",
    0x21: "Distance with MIL on (km)",
    0x22: "Fuel Rail Pressure rel. to manifold (kPa)",
    0x23: "Fuel Rail Gauge Pressure (kPa)",
    0x2C: "Commanded EGR (%)",
    0x2D: "EGR Error (%)",
    0x2E: "Commanded evaporative purge (%)",
    0x2F: "Fuel Tank Level Input (%)",
    0x30: "Warm-ups since codes cleared",
    0x31: "Distance since codes cleared (km)",
    0x32: "Evap System Vapor Pressure (Pa)",
    0x33: "Absolute Barometric Pressure (kPa)",
    0x40: "PIDs supported [41-60]",
    0x41: "Monitor status this drive cycle",
    0x42: "Control module voltage (V)",
    0x43: "Absolute load value (%)",
    0x44: "Commanded Air-Fuel Equivalence Ratio (lambda)",
    0x45: "Relative throttle position (%)",
    0x46: "Ambient air temperature (°C)",
    0x47: "Absolute throttle position B (%)",
    0x48: "Absolute throttle position C (%)",
    0x49: "Accelerator pedal position D (%)",
    0x4A: "Accelerator pedal position E (%)",
    0x4B: "Accelerator pedal position F (%)",
    0x4C: "Commanded throttle actuator (%)",
    0x4D: "Time run with MIL on (min)",
    0x4E: "Time since trouble codes cleared (min)",
    0x51: "Fuel Type",
    0x52: "Ethanol fuel (%)",
    0x59: "Fuel rail absolute pressure (kPa)",
    0x5A: "Relative accelerator pedal position (%)",
    0x5C: "Engine oil temperature / EOT (°C)",
    0x5D: "Fuel injection timing (°)",
    0x5E: "Engine fuel rate (L/h)",
    0x5F: "Emission requirements vehicle designed for",
    0x60: "PIDs supported [61-80]",
    0x61: "Driver's demand engine torque (%)",
    0x62: "Actual engine torque (%)",
    0x63: "Engine reference torque (Nm)",
    0x64: "Engine percent torque data",
}


def send_cmd(sock, cmd, wait=0.3):
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
            if b">" in buf:
                break
    except socket.timeout:
        pass
    text = buf.decode("ascii", errors="replace")
    text = text.replace(cmd, "").replace(">", "").replace("\r", "\n")
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def extract_hex_data(resp):
    """De una respuesta multilínea, extrae líneas que parecen datos hex."""
    hex_lines = []
    for line in resp.split("\n"):
        clean = line.replace(" ", "").upper()
        if clean and all(c in "0123456789ABCDEF" for c in clean) and len(clean) >= 4:
            hex_lines.append(clean)
    return hex_lines


def query_pid_bitmap(sock, base_pid, wait=2.0):
    """Consulta un PID de bitmap (00, 20, 40, 60) y devuelve los 4 bytes."""
    cmd = f"01{base_pid:02X}"
    resp = send_cmd(sock, cmd, wait=wait)

    hex_lines = extract_hex_data(resp)
    if not hex_lines:
        return None, resp

    # Buscar el patrón "41XX" en las líneas hex
    target = f"41{base_pid:02X}"
    for data in hex_lines:
        idx = data.find(target)
        if idx != -1 and len(data) >= idx + 12:
            bitmap_hex = data[idx + 4:idx + 12]
            try:
                return bytes.fromhex(bitmap_hex), resp
            except ValueError:
                continue
    return None, resp


def decode_supported_pids(bitmap, base):
    """Devuelve lista de PIDs soportados según el bitmap (4 bytes = 32 bits).

    Bit MSB del primer byte = PID base+1, bit LSB del último byte = PID base+32.
    """
    supported = []
    for byte_idx in range(4):
        byte = bitmap[byte_idx]
        for bit in range(8):
            # MSB del byte = primer PID del grupo de 8
            pid_offset = byte_idx * 8 + (7 - bit) + 1
            if byte & (1 << bit):
                supported.append(base + pid_offset)
    return supported


def main():
    print(f"Conectando a ELM327 en {HOST}:{PORT}...")
    try:
        sock = socket.create_connection((HOST, PORT), timeout=TIMEOUT)
    except (socket.timeout, ConnectionRefusedError, OSError) as e:
        print(f"ERROR: {e}")
        return 1
    print("Conexión TCP OK.\n")

    # Handshake limpio (headers OFF para parseo más simple)
    print("=== Handshake ===")
    print(f"ATZ : {send_cmd(sock, 'ATZ', wait=1.5)}")
    print(f"ATE0: {send_cmd(sock, 'ATE0')}")
    print(f"ATL0: {send_cmd(sock, 'ATL0')}")
    print(f"ATH0: {send_cmd(sock, 'ATH0')}")
    print(f"ATS0: {send_cmd(sock, 'ATS0')}")
    print(f"ATSP0 (auto-detect): {send_cmd(sock, 'ATSP0')}")
    print(f"ATRV (voltaje): {send_cmd(sock, 'ATRV')}")

    # Consultar los 4 rangos de PIDs (01-20, 21-40, 41-60, 61-80)
    print("\n=== Consultando bitmaps de PIDs soportados ===")
    all_supported = []
    ranges = [(0x00, 8.0), (0x20, 2.0), (0x40, 2.0), (0x60, 2.0)]

    for base, wait in ranges:
        cmd_label = f"01{base:02X}"
        bitmap, raw = query_pid_bitmap(sock, base, wait=wait)

        if bitmap is None:
            if base == 0x00:
                print(f"\n❌ {cmd_label}: no se obtuvo respuesta válida.")
                print(f"   Respuesta cruda:\n   {raw}")
                sock.close()
                return 1
            print(f"  {cmd_label}: no soportado (fin de rango)")
            break

        pids_here = decode_supported_pids(bitmap, base)
        all_supported.extend(pids_here)
        print(f"  {cmd_label}: bitmap = {bitmap.hex().upper()} → {len(pids_here)} PIDs en rango")

        # ¿Hay más rangos?
        next_range = base + 0x20
        if next_range not in pids_here:
            print(f"  → PID {next_range:02X} no soportado, no hay más rangos")
            break

    # Tabla final
    print(f"\n{'=' * 70}")
    print(f"PIDs SOPORTADOS POR LA ECU ({len(all_supported)} total)")
    print(f"{'=' * 70}\n")
    print(f"{'PID':<4} {'Cmd':<6} {'Descripción':<55}")
    print("-" * 70)
    for pid in sorted(all_supported):
        name = PID_NAMES.get(pid, "(no en tabla — buscar referencia OBD2)")
        marker = " ⭐" if pid in USEFUL else ""
        print(f"{pid:02X}   01{pid:02X}    {name}{marker}")

    print(f"\n⭐ = útil para nuestro objetivo")
    print("\nLeyenda de PIDs prioritarios:")
    print("  RPM=0C  Speed=0D  TPS=11  MAP=0B  IAT=0F  EOT=5C")
    print("  FuelRate=5E (consumo L/h)  CtrlVoltage=42  AmbAir=46")

    sock.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
