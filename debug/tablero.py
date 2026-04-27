#!/usr/bin/env python3
"""
Tablero virtual para Royal Enfield Interceptor 650.

Reemplaza el cuadro de instrumentos físico con un display en terminal:
- Velocidad y RPM en grande con barras y zonas de color
- Marcha estimada (calculada desde RPM/velocidad y ratios de transmisión)
- Temperatura de aceite con alertas (frío/normal/alto/peligro)
- Voltaje del sistema (¿alternador cargando bien?)
- Throttle, carga, MAP, IAT
- Consumo estimado de combustible (L/h, km/L)
- Alertas activas en el momento

Uso:
    python3 tablero.py                   # 1 Hz update (default)
    python3 tablero.py --interval 0.5    # 2 Hz, más fluido pero pega más al ELM
    python3 tablero.py --csv ride.csv    # log opcional para análisis
    python3 tablero.py --ve 0.85         # volumetric efficiency para cálculo fuel
"""

import socket
import time
import sys
import argparse
import csv
import shutil
from datetime import datetime

HOST = "192.168.0.10"
PORT = 35000
TIMEOUT = 5.0

# Specs del Interceptor 650 (manual p.4)
DISPLACEMENT_L = 0.648
M_AIR = 28.97
R_GAS = 8.314
AFR_STOICH = 14.7
GASOLINE_DENSITY = 745.7

# Transmisión: ratios para cálculo de marcha
GEAR_RATIOS = {1: 2.615, 2: 1.813, 3: 1.429, 4: 1.190, 5: 1.040, 6: 0.962}
PRIMARY_RATIO = 2.05
SECONDARY_RATIO = 2.533
TIRE_CIRCUM_M = 2.008  # 130/70 R18 trasera

# Umbrales de alerta
EOT_COLD_MAX = 60     # debajo: motor frío todavía
EOT_NORMAL_MAX = 105  # arriba: caliente
EOT_WARNING = 115     # arriba: alarma
EOT_DANGER = 125      # arriba: detener moto

RPM_REDLINE = 7400    # cutoff @ 7000-7400 RPM por manual p.133
RPM_YELLOW = 6000
RPM_GREEN_MAX = 5000

VOLT_LOW = 12.0
VOLT_NORMAL = 13.5
VOLT_HIGH = 14.8

# ANSI
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
WHITE = "\033[97m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"
CLEAR_SCREEN = "\033[2J\033[H"


def send_cmd(sock, cmd, wait=0.05):
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
    cmd = f"01{pid:02X}"
    resp = send_cmd(sock, cmd)
    target = f"41{pid:02X}"
    for line in resp.split("\n"):
        clean = line.replace(" ", "").upper()
        idx = clean.find(target)
        if idx != -1:
            data_hex = clean[idx + 4:]
            data_hex = data_hex[:len(data_hex) - (len(data_hex) % 2)]
            try:
                return bytes.fromhex(data_hex)
            except ValueError:
                continue
    return None


def decode_pid(pid, data):
    if data is None or len(data) == 0:
        return None
    A = data[0]
    B = data[1] if len(data) > 1 else 0
    if pid == 0x04: return A * 100.0 / 255
    if pid == 0x0B: return float(A)
    if pid == 0x0C: return ((A * 256) + B) / 4.0
    if pid == 0x0D: return float(A)
    if pid == 0x0F: return A - 40.0
    if pid == 0x11: return A * 100.0 / 255
    if pid == 0x5C: return A - 40.0
    return None


def estimate_gear(rpm, speed_kmh):
    """Estima marcha desde ratio RPM_motor / RPM_rueda y los ratios documentados."""
    if speed_kmh < 5 or rpm < 800:
        return None
    speed_ms = speed_kmh / 3.6
    wheel_rpm = (speed_ms / TIRE_CIRCUM_M) * 60
    if wheel_rpm < 1:
        return None
    actual_ratio = rpm / wheel_rpm / (PRIMARY_RATIO * SECONDARY_RATIO)
    best = min(GEAR_RATIOS.items(), key=lambda kv: abs(kv[1] - actual_ratio))
    if abs(best[1] - actual_ratio) / best[1] < 0.15:
        return best[0]
    return None


def calc_fuel_lh(map_kpa, rpm, iat_c, ve):
    if rpm < 100 or map_kpa < 1:
        return 0.0
    iat_k = max(iat_c + 273.15, 200.0)
    maf_gs = (map_kpa * DISPLACEMENT_L * rpm * ve * M_AIR) / (R_GAS * iat_k * 120)
    fuel_gs = maf_gs / AFR_STOICH
    return fuel_gs * 3600 / GASOLINE_DENSITY


def bar(value, max_value, width=30, color=""):
    if value is None or max_value <= 0:
        return "─" * width
    filled = max(0, min(width, int((value / max_value) * width)))
    s = "█" * filled + "░" * (width - filled)
    return f"{color}{s}{RESET}" if color else s


def color_for_rpm(rpm):
    if rpm < RPM_GREEN_MAX: return GREEN
    if rpm < RPM_YELLOW: return YELLOW
    return RED


def color_for_eot(eot):
    if eot < EOT_COLD_MAX: return CYAN
    if eot < EOT_NORMAL_MAX: return GREEN
    if eot < EOT_WARNING: return YELLOW
    return RED


def color_for_voltage(v):
    if v < VOLT_LOW or v > VOLT_HIGH: return RED
    if v >= VOLT_NORMAL - 0.3: return GREEN
    return YELLOW


def color_for_speed(s):
    if s > 100: return RED
    if s > 80: return YELLOW
    return WHITE


def render(data, args, session):
    rpm = data.get("rpm", 0) or 0
    speed = data.get("speed", 0) or 0
    tps = data.get("tps", 0) or 0
    map_kpa = data.get("map", 0) or 0
    iat = data.get("iat", 25) if data.get("iat") is not None else 25
    eot = data.get("eot", 0) or 0
    load = data.get("load", 0) or 0
    voltage = data.get("voltage", 0) or 0
    fuel_lh = data.get("fuel_lh", 0) or 0
    gear = data.get("gear")

    width = max(70, shutil.get_terminal_size((80, 24)).columns)
    line = "─" * (width - 2)

    out = [CLEAR_SCREEN]
    out.append(f"{BOLD}╔{line}╗{RESET}")
    title = " ROYAL ENFIELD INTERCEPTOR 650 — TABLERO VIRTUAL "
    out.append(f"{BOLD}║{title:<{width - 2}}║{RESET}")
    out.append(f"{BOLD}╠{line}╣{RESET}")

    # Velocidad y RPM grandes
    sp_color = color_for_speed(speed)
    rpm_color = color_for_rpm(rpm)
    out.append("")
    out.append(f"   {BOLD}VELOCIDAD{RESET}                              {BOLD}RPM{RESET}")
    out.append(f"   {sp_color}{BOLD}{int(speed):>4} km/h{RESET}                          "
               f"{rpm_color}{BOLD}{int(rpm):>5}{RESET}")
    out.append(f"   {bar(speed, 200, 30, sp_color)}    {bar(rpm, RPM_REDLINE, 25, rpm_color)}")
    out.append(f"   {DIM}0{' ' * 26}200    0{' ' * 21}7400{RESET}")

    # Línea de info media: marcha + throttle + carga
    gear_str = f"{gear}ª" if gear else ("N" if speed < 5 and rpm > 0 else "—")
    gear_color = BOLD + GREEN if gear else DIM
    out.append("")
    out.append(f"   MARCHA: {gear_color}{gear_str:<3}{RESET}    "
               f"THROTTLE: {tps:>5.1f}%    "
               f"CARGA: {load:>5.1f}%    "
               f"MAP: {map_kpa:>3.0f} kPa")

    # Motor
    out.append(f"\n   {DIM}─── MOTOR ─{'─' * (width - 14)}{RESET}")
    eot_label = "DETENER MOTO" if eot >= EOT_DANGER else \
                "ALTO" if eot >= EOT_WARNING else \
                "Normal" if eot >= EOT_COLD_MAX else \
                "Frío (calentando)"
    out.append(f"   Aceite (EOT):  {color_for_eot(eot)}{eot:>5.0f}°C{RESET}   "
               f"{color_for_eot(eot)}{eot_label}{RESET}")
    out.append(f"   Aire (IAT):    {iat:>5.0f}°C")

    volt_label = "Alternador no carga" if voltage < VOLT_LOW else \
                 "REG fallando?" if voltage > VOLT_HIGH else \
                 "Cargando OK" if voltage >= VOLT_NORMAL - 0.3 else \
                 "Bajo (motor apagado o batería débil)"
    out.append(f"   Voltaje:       {color_for_voltage(voltage)}{voltage:>5.1f}V{RESET}   "
               f"{volt_label}")

    # Combustible
    out.append(f"\n   {DIM}─── COMBUSTIBLE (estimado) {'─' * (width - 31)}{RESET}")
    out.append(f"   Consumo ahora: {fuel_lh:>5.2f} L/h")
    if speed > 5 and fuel_lh > 0.05:
        kmpl = speed / fuel_lh
        l100 = (fuel_lh / speed) * 100
        out.append(f"   Eficiencia:    {kmpl:>5.1f} km/L  ({l100:.1f} L/100km)")
    else:
        out.append(f"   Eficiencia:    {DIM}— (necesita estar en movimiento){RESET}")

    # Stats de sesión
    out.append(f"\n   {DIM}─── SESIÓN {'─' * (width - 15)}{RESET}")
    elapsed_min = (time.time() - session["start"]) / 60
    out.append(f"   Tiempo:    {elapsed_min:>5.1f} min       "
               f"Vmax: {session['v_max']:>3.0f} km/h     "
               f"RPMmax: {session['rpm_max']:>5.0f}")
    out.append(f"   EOT max:   {session['eot_max']:>5.1f}°C       "
               f"Combust. acumulado: {session['fuel_total']:.3f} L")

    # Alertas
    out.append(f"\n   {DIM}─── ALERTAS {'─' * (width - 16)}{RESET}")
    alerts = []
    if eot >= EOT_DANGER:
        alerts.append(f"{BOLD}{RED}🚨 EOT CRÍTICA: detené la moto YA{RESET}")
    elif eot >= EOT_WARNING:
        alerts.append(f"{YELLOW}⚠  EOT alta: bajá ritmo{RESET}")
    if rpm > RPM_REDLINE - 200:
        alerts.append(f"{RED}⚠  RPM en redline ({int(rpm)}){RESET}")
    if voltage < VOLT_LOW and rpm > 1000:
        alerts.append(f"{RED}⚠  Voltaje bajo con motor andando — alternador?{RESET}")
    if voltage > VOLT_HIGH:
        alerts.append(f"{RED}⚠  Voltaje muy alto — chequear regulador{RESET}")
    if eot < EOT_COLD_MAX and rpm > 4000:
        alerts.append(f"{YELLOW}⚠  Motor frío + RPM alto — esperá que caliente{RESET}")
    if not alerts:
        alerts.append(f"{GREEN}✓ Todo OK{RESET}")
    for a in alerts:
        out.append(f"   {a}")

    # Footer
    ts = datetime.now().strftime("%H:%M:%S")
    out.append("")
    out.append(f"{DIM}   {ts}   |   VE={args.ve}   |   Ctrl+C para salir{RESET}")
    out.append(f"{BOLD}╚{line}╝{RESET}")
    return "\n".join(out)


def main():
    p = argparse.ArgumentParser(description="Tablero virtual para Interceptor 650")
    p.add_argument("--interval", type=float, default=1.0)
    p.add_argument("--ve", type=float, default=0.85)
    p.add_argument("--csv", help="opcional: log a CSV")
    args = p.parse_args()

    print(f"Conectando a {HOST}:{PORT}...")
    try:
        sock = socket.create_connection((HOST, PORT), timeout=TIMEOUT)
    except OSError as e:
        print(f"ERROR: {e}")
        return 1
    print("Conexión OK. Inicializando ELM327...")

    send_cmd(sock, "ATZ", wait=1.5)
    send_cmd(sock, "ATE0")
    send_cmd(sock, "ATL0")
    send_cmd(sock, "ATH0")
    send_cmd(sock, "ATS0")
    send_cmd(sock, "ATSP0")
    print("Auto-detect protocolo (puede tardar)...")
    send_cmd(sock, "0100", wait=8.0)
    print("Listo. Iniciando tablero...\n")
    time.sleep(1)

    pids = [
        (0x0C, "rpm"),
        (0x0D, "speed"),
        (0x11, "tps"),
        (0x0B, "map"),
        (0x0F, "iat"),
        (0x5C, "eot"),
        (0x04, "load"),
    ]

    csv_file = None
    csv_writer = None
    if args.csv:
        csv_file = open(args.csv, "w", newline="")
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow([
            "timestamp", "rpm", "speed", "tps", "map", "iat", "eot",
            "load", "voltage", "fuel_lh", "gear",
        ])

    session = {
        "start": time.time(),
        "v_max": 0.0,
        "rpm_max": 0.0,
        "eot_max": 0.0,
        "fuel_total": 0.0,
        "last_t": time.time(),
    }

    try:
        while True:
            t0 = time.time()
            data = {}
            for pid, name in pids:
                v = decode_pid(pid, query_pid(sock, pid))
                if v is not None:
                    data[name] = v

            v_str = send_cmd(sock, "ATRV")
            try:
                data["voltage"] = float(v_str.replace("V", "").strip())
            except (ValueError, AttributeError):
                data["voltage"] = 0.0

            data["fuel_lh"] = calc_fuel_lh(
                data.get("map", 0), data.get("rpm", 0),
                data.get("iat", 25) if data.get("iat") is not None else 25,
                args.ve,
            )
            data["gear"] = estimate_gear(data.get("rpm", 0), data.get("speed", 0))

            # Update sesión
            now = time.time()
            dt_h = (now - session["last_t"]) / 3600
            session["v_max"] = max(session["v_max"], data.get("speed", 0) or 0)
            session["rpm_max"] = max(session["rpm_max"], data.get("rpm", 0) or 0)
            session["eot_max"] = max(session["eot_max"], data.get("eot", 0) or 0)
            session["fuel_total"] += (data["fuel_lh"]) * dt_h
            session["last_t"] = now

            sys.stdout.write(render(data, args, session))
            sys.stdout.flush()

            if csv_writer:
                ts = datetime.now().strftime("%H:%M:%S")
                csv_writer.writerow([
                    ts, f"{data.get('rpm', 0):.0f}",
                    f"{data.get('speed', 0):.0f}", f"{data.get('tps', 0):.2f}",
                    f"{data.get('map', 0):.1f}", f"{data.get('iat', 0):.1f}",
                    f"{data.get('eot', 0):.1f}", f"{data.get('load', 0):.2f}",
                    f"{data.get('voltage', 0):.2f}",
                    f"{data.get('fuel_lh', 0):.3f}", data.get("gear", ""),
                ])
                csv_file.flush()

            elapsed = time.time() - t0
            if elapsed < args.interval:
                time.sleep(args.interval - elapsed)
    except KeyboardInterrupt:
        print(f"\n{RESET}\nDetenido. Resumen:")
        elapsed_min = (time.time() - session["start"]) / 60
        print(f"  Duración: {elapsed_min:.1f} min")
        print(f"  Velocidad máx: {session['v_max']:.0f} km/h")
        print(f"  RPM máx: {session['rpm_max']:.0f}")
        print(f"  EOT máx: {session['eot_max']:.1f}°C")
        print(f"  Combust. estimado: {session['fuel_total']:.3f} L")
    except OSError as e:
        print(f"\n{RESET}ERROR conexión: {e}")
    finally:
        if csv_file:
            csv_file.close()
            print(f"  CSV: {args.csv}")
        sock.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
