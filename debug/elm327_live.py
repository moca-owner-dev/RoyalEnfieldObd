#!/usr/bin/env python3
"""
Live data + cálculo de consumo para Royal Enfield Interceptor 650.

Lee RPM, velocidad, throttle, MAP, IAT, EOT, engine load en loop, y calcula:
  - MAF (mass air flow) en g/s usando fórmula speed-density
  - Consumo de combustible en g/s y L/h (asumiendo AFR estequiométrico 14.7)
  - Eficiencia en km/L cuando hay velocidad

Uso:
    python3 elm327_live.py                       # display en terminal a 1 Hz
    python3 elm327_live.py --csv mi_log.csv      # también guarda CSV
    python3 elm327_live.py --interval 0.5        # segundos entre lecturas
    python3 elm327_live.py --ve 0.90             # ajustar volumetric efficiency

Calibración:
  Por defecto VE=0.85 (genérico naturally aspirated). Para mejor precisión:
  1. Llená el tanque, anotá el odómetro
  2. Andá un trayecto largo logueando con --csv
  3. Llená de nuevo, anotá litros gastados y km recorridos
  4. Compará con el promedio de fuel_lh × tiempo_total del CSV
  5. Ajustá --ve hasta que cuadre (típico entre 0.75 y 0.95)
"""

import socket
import time
import sys
import argparse
import csv
from datetime import datetime

HOST = "192.168.0.10"
PORT = 35000
TIMEOUT = 5.0

# Constantes físicas y del motor
DISPLACEMENT_L = 0.648     # 648 cc del Interceptor 650
M_AIR = 28.97              # g/mol — masa molar del aire
R_GAS = 8.314              # J/(mol·K) — constante de gas ideal
AFR_STOICH = 14.7          # AFR estequiométrico para gasolina
GASOLINE_DENSITY = 745.7   # g/L — densidad de gasolina


def send_cmd(sock, cmd, wait=0.05):
    """Envía un comando AT/OBD y devuelve respuesta limpia."""
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


def query_pid(sock, pid):
    """Consulta un PID Mode 01 y devuelve los bytes de datos (post 41XX)."""
    cmd = f"01{pid:02X}"
    resp = send_cmd(sock, cmd)
    target = f"41{pid:02X}"
    for line in resp.split("\n"):
        clean = line.replace(" ", "").upper()
        idx = clean.find(target)
        if idx != -1:
            data_hex = clean[idx + 4:]
            # Tomar bytes pares (la respuesta puede tener relleno)
            data_hex = data_hex[:len(data_hex) - (len(data_hex) % 2)]
            try:
                return bytes.fromhex(data_hex)
            except ValueError:
                continue
    return None


def decode_pid(pid, data):
    """Decodifica los bytes de un PID estándar OBD2 a su valor real."""
    if data is None or len(data) == 0:
        return None
    A = data[0]
    B = data[1] if len(data) > 1 else 0
    if pid == 0x04: return A * 100.0 / 255           # engine load %
    if pid == 0x0B: return float(A)                  # MAP kPa
    if pid == 0x0C: return ((A * 256) + B) / 4.0     # RPM
    if pid == 0x0D: return float(A)                  # speed km/h
    if pid == 0x0E: return A / 2.0 - 64              # timing advance °
    if pid == 0x0F: return A - 40.0                  # IAT °C
    if pid == 0x11: return A * 100.0 / 255           # TPS %
    if pid == 0x5C: return A - 40.0                  # EOT °C
    return None


def calc_fuel_rate(map_kpa, rpm, iat_c, ve):
    """Speed-density: estima MAF, luego consumo asumiendo AFR estequiométrico.

    Returns: (maf_gs, fuel_gs, fuel_lh)
    """
    if rpm < 100 or map_kpa < 1:
        return 0.0, 0.0, 0.0
    iat_k = max(iat_c + 273.15, 200.0)  # clamp por si IAT lee basura
    # MAF [g/s] = MAP_kPa × Disp_L × RPM × VE × M_air / (R × IAT_K × 120)
    # /120 = /60 (rpm→rps) × /2 (4-stroke: una admisión cada 2 revoluciones)
    maf_gs = (map_kpa * DISPLACEMENT_L * rpm * ve * M_AIR) / (R_GAS * iat_k * 120)
    fuel_gs = maf_gs / AFR_STOICH
    fuel_lh = fuel_gs * 3600 / GASOLINE_DENSITY
    return maf_gs, fuel_gs, fuel_lh


def main():
    p = argparse.ArgumentParser(description="Live OBD data + fuel calc para RE 650")
    p.add_argument("--csv", help="archivo CSV para logging")
    p.add_argument("--interval", type=float, default=1.0, help="segundos entre lecturas")
    p.add_argument("--ve", type=float, default=0.85, help="volumetric efficiency 0-1")
    args = p.parse_args()

    print(f"Conectando a {HOST}:{PORT}...")
    try:
        sock = socket.create_connection((HOST, PORT), timeout=TIMEOUT)
    except OSError as e:
        print(f"ERROR: {e}")
        return 1
    print("Conexión OK.")

    # Handshake silencioso
    send_cmd(sock, "ATZ", wait=1.5)
    send_cmd(sock, "ATE0")
    send_cmd(sock, "ATL0")
    send_cmd(sock, "ATH0")
    send_cmd(sock, "ATS0")
    send_cmd(sock, "ATSP0")
    print("Auto-detectando protocolo...")
    send_cmd(sock, "0100", wait=8.0)
    print(f"Listo. VE={args.ve}, intervalo={args.interval}s. Ctrl+C para salir.\n")

    pids = [
        (0x0C, "RPM"),
        (0x0D, "Speed"),
        (0x11, "TPS"),
        (0x0B, "MAP"),
        (0x0F, "IAT"),
        (0x5C, "EOT"),
        (0x04, "Load"),
    ]

    csv_file = None
    csv_writer = None
    if args.csv:
        csv_file = open(args.csv, "w", newline="")
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow([
            "timestamp", "rpm", "speed_kmh", "tps_pct", "map_kpa",
            "iat_c", "eot_c", "load_pct", "maf_gs", "fuel_gs",
            "fuel_lh", "kmpl",
        ])

    # Header de tabla
    hdr = (f"{'Time':<10} {'RPM':>5} {'kmh':>4} {'TPS%':>5} {'MAP':>4} "
           f"{'IAT':>4} {'EOT':>4} {'Ld%':>5} {'L/h':>6} {'km/L':>5}")
    print(hdr)
    print("-" * len(hdr))

    try:
        while True:
            t0 = time.time()
            values = {}
            for pid, name in pids:
                data = query_pid(sock, pid)
                values[name] = decode_pid(pid, data)

            rpm = values.get("RPM") or 0.0
            speed = values.get("Speed") or 0.0
            tps = values.get("TPS") or 0.0
            map_kpa = values.get("MAP") or 0.0
            iat = values.get("IAT") if values.get("IAT") is not None else 25.0
            eot = values.get("EOT") or 0.0
            load = values.get("Load") or 0.0

            maf_gs, fuel_gs, fuel_lh = calc_fuel_rate(map_kpa, rpm, iat, args.ve)
            kmpl = (speed / fuel_lh) if (fuel_lh > 0.01 and speed > 0) else 0.0

            ts = datetime.now().strftime("%H:%M:%S")
            print(f"{ts:<10} {rpm:>5.0f} {speed:>4.0f} {tps:>5.1f} {map_kpa:>4.0f} "
                  f"{iat:>4.0f} {eot:>4.0f} {load:>5.1f} {fuel_lh:>6.2f} {kmpl:>5.1f}")

            if csv_writer:
                csv_writer.writerow([
                    ts, f"{rpm:.0f}", f"{speed:.0f}", f"{tps:.2f}",
                    f"{map_kpa:.1f}", f"{iat:.1f}", f"{eot:.1f}", f"{load:.2f}",
                    f"{maf_gs:.4f}", f"{fuel_gs:.4f}", f"{fuel_lh:.3f}", f"{kmpl:.2f}",
                ])
                csv_file.flush()

            elapsed = time.time() - t0
            if elapsed < args.interval:
                time.sleep(args.interval - elapsed)
    except KeyboardInterrupt:
        print("\n\nDetenido.")
    except OSError as e:
        print(f"\nERROR de conexión: {e}")
    finally:
        if csv_file:
            csv_file.close()
            print(f"CSV guardado: {args.csv}")
        sock.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
