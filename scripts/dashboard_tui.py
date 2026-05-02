#!/usr/bin/env python3
"""Pip-Boy style dashboard para Royal Enfield Interceptor 650.

VERSIÓN STATIC: valores hardcodeados de mockup. Diseñado para 60 cols x 40 rows
(LCD 480x320 con font VGA8x8).

Para verlo en el LCD del Pi:
    ssh -t pipboy@10.42.0.249 "sudo ~/RoyalEnfieldObd/scripts/show-tui.sh"
"""
import re
import sys
import datetime

# ─── Pip-Boy palette (ANSI con bg=black forzado) ───
G = "\033[40;1;32m"      # bg black + green bold (texto principal)
GB = "\033[40;1;92m"     # bg black + bright green bold (números)
g = "\033[40;32m"        # bg black + green dim (labels)
R = "\033[40;1;91m"      # bg black + red
A = "\033[40;1;93m"      # bg black + yellow
RST = "\033[0m"
CLR = "\033[40m\033[2J\033[H"

# ─── Mockup data ───
S = {
    "speed": 87, "rpm": 4523, "gear": 4,
    "eot": 87, "iat": 28, "voltage": 13.8,
    "tps": 35.0, "load": 42, "fuel_l_100km": 4.2,
    "tank_l": 2.14, "tank_km": 23.4, "tank_avg": 4.5, "tank_cost": 21.34,
    "session_min": 12, "session_vmax": 110, "session_rpmmax": 7044,
    "uptime": "3d 14h 22m", "ip": "192.168.10.1", "ssid": "Interceptor-Pi",
    "mock_active": False,
    "alerts": [],
}

WIDTH = 60
SPEED_MAX = 200
RPM_MAX = 8500
RPM_REDLINE = 7000

ANSI_RE = re.compile(r"\033\[[0-9;]*m")


def visible_len(s):
    return len(ANSI_RE.sub("", s))


def line(content=""):
    """Wrap content in | borders, padded to WIDTH chars total."""
    pad = WIDTH - 2 - visible_len(content)
    return f"{G}|{content}{' ' * max(0, pad)}|{RST}"


def hdr(content="", char="="):
    if not content:
        return f"{G}+{char * (WIDTH - 2)}+{RST}"
    pad = WIDTH - 2 - visible_len(content)
    left = pad // 2
    right = pad - left
    return f"{G}+{char * left}{content}{char * right}+{RST}"


def bar(value, max_val, width, redline=None):
    pct = max(0.0, min(1.0, value / max_val))
    filled = int(pct * width)
    s = "#" * filled + "." * (width - filled)
    if redline is not None:
        rp = int(redline / max_val * width)
        if 0 < rp < width:
            s = s[:rp] + "|" + s[rp + 1:]
    return s


def status_eot(eot):
    if eot > 115: return R, "[OVERHEAT]"
    if eot > 105: return A, "[ HOT  ]"
    if eot >= 60: return G, "[ NORM ]"
    return g, "[ COLD ]"


def status_volt(v):
    if v < 12.0: return R, "[LOW]"
    if v < 13.0: return A, "[ OK]"
    return G, "[ OK]"


def render(s):
    rpm_c = R if s["rpm"] >= RPM_REDLINE else GB
    eot_c, eot_lbl = status_eot(s["eot"])
    bat_c, bat_lbl = status_volt(s["voltage"])

    sp_bar = bar(s["speed"], SPEED_MAX, 10)
    rpm_bar = bar(s["rpm"], RPM_MAX, 10, redline=RPM_REDLINE)
    online = f"{G}[ONLINE]{RST}" if not s["mock_active"] else f"{A}[ MOCK ]{RST}"
    mock_str = "1" if s["mock_active"] else "0"
    gear_str = str(s["gear"]) if s["gear"] else "-"

    alert_line = "[ ALL SYSTEMS NOMINAL ]"
    alert_color = G
    if s.get("alerts"):
        alert_line = "! " + " | ".join(s["alerts"]) + " !"
        alert_color = R

    now = datetime.datetime.now().strftime("%Y-%m-%d  %H:%M:%S")

    # Tres paneles de 14 cols cada uno: SPEED, RPM, GEAR
    # Espaciado: 2 left + 14 + 1 + 14 + 1 + 14 + 12 right = 58 inner = 60 con bordes
    # Cada panel tiene 12 cols de contenido (entre los | internos)
    panel_top = "+-- SPEED ---+ +--- RPM ----+ +-- GEAR ----+"
    panel_bot = "+------------+ +------------+ +------------+"
    panel_blank = "|            | |            | |            |"
    panel_value = f"|     {GB}{s['speed']:>3}{G}    | |    {rpm_c}{s['rpm']:>4}{G}    | |     {GB}{gear_str:^1}{G}      |"
    panel_unit = "|    km/h    | |  /  8500   | |            |"
    panel_bar = f"| {GB}{sp_bar}{G} | | {rpm_c}{rpm_bar}{G} | |            |"

    lines = [
        # Header con título y fecha
        CLR + hdr(" ROBCO INDUSTRIES "),
        line(f"   ROYAL ENFIELD 650  -  INTERCEPTOR DIAGNOSTIC"),
        line(f"   TERMINAL ID: PIP-OS v3.4.1   {now}"),
        hdr(),
        line(),
        # Tres paneles principales
        line(f"  {panel_top}  "),
        line(f"  {panel_blank}  "),
        line(f"  {panel_value}  "),
        line(f"  {panel_unit}  "),
        line(f"  {panel_blank}  "),
        line(f"  {panel_bar}  "),
        line(f"  {panel_blank}  "),
        line(f"  {panel_bot}  "),
        line(),
        # Strip secundario
        hdr(),
        line(),
        line(f"   EOT  {eot_c}{s['eot']:>3}C{G} {eot_c}{eot_lbl}{G}    IAT  {GB}{s['iat']:>3}{G}C    BAT  {bat_c}{s['voltage']:>4.1f}V{G} {bat_c}{bat_lbl}{G}"),
        line(),
        line(f"   THR  {GB}{s['tps']:>3.0f}{G}%      LOAD  {GB}{s['load']:>3}{G}%      L/100km  {GB}{s['fuel_l_100km']:>4.1f}{G}"),
        line(),
        # Alerts
        hdr(),
        line(f"   ALERTS:  {alert_color}{alert_line}{G}"),
        # Tank + Session
        hdr(),
        line(),
        line(f"   TANK SINCE FILL              SESSION"),
        line(),
        line(f"   - {GB}{s['tank_l']:>5.2f}{G} L / {GB}{s['tank_km']:>5.1f}{G} km     - ELAPSED  {GB}{s['session_min']:>3}{G} min"),
        line(f"   - AVG    {GB}{s['tank_avg']:>4.1f}{G} L/100km     - MAX SPD  {GB}{s['session_vmax']:>3}{G} km/h"),
        line(f"   - COST   {GB}Q{s['tank_cost']:>6.2f}{G}        - MAX RPM  {GB}{s['session_rpmmax']:>4}{G}"),
        line(),
        # Status
        hdr(),
        line(f"   > NETWORK   {GB}{s['ssid']}{G} @ {GB}{s['ip']}{G}"),
        line(f"   > MOCK_OBD  {GB}{mock_str}{G}    UPTIME  {GB}{s['uptime']}{G}"),
        line(f"   > MODE      {online}"),
        hdr(char="="),
    ]
    return "\n".join(lines) + RST + "\n"


if __name__ == "__main__":
    sys.stdout.write(render(S))
    sys.stdout.flush()
