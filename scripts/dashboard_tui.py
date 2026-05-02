#!/usr/bin/env python3
"""Pip-Boy style dashboard para Royal Enfield Interceptor 650.

VERSIÓN STATIC: valores hardcodeados de mockup. La idea es ver cómo queda
en el LCD del Pi (tty1) antes de conectarlo al /api/data real.

Para verlo en el LCD del Pi:
    ssh -t pipboy@10.42.0.249 "sudo ~/RoyalEnfieldObd/scripts/show-tui.sh"

Diseñado para 60 cols x ~40 rows (LCD 480x320 con font VGA8x8).
"""
import re
import sys

# ─── Pip-Boy palette (ANSI) ───
G = "\033[40;1;32m"      # bg black + green bold
GB = "\033[40;1;92m"     # bg black + bright green bold
g = "\033[40;32m"        # bg black + green dim
R = "\033[40;1;91m"      # bg black + bright red
A = "\033[40;1;93m"      # bg black + bright yellow
RST = "\033[0m"
# Pinta toda la pantalla negra antes del primer print, así no queda bg azul
# del default de la consola del kernel
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
    "alerts": [],  # ej: ["EOT HIGH", "BATTERY LOW"]
}

WIDTH = 60
SPEED_MAX = 200
RPM_MAX = 8500
RPM_REDLINE = 7000

ANSI_RE = re.compile(r"\033\[[0-9;]*m")

# ─── Big block digits (7 filas x 4 cols por dígito) — estilo 7-segment ───
DIGITS = {
    "0": ["####", "#  #", "#  #", "#  #", "#  #", "#  #", "####"],
    "1": ["  # ", " ## ", "  # ", "  # ", "  # ", "  # ", "####"],
    "2": ["####", "   #", "   #", "####", "#   ", "#   ", "####"],
    "3": ["####", "   #", "   #", "####", "   #", "   #", "####"],
    "4": ["#  #", "#  #", "#  #", "####", "   #", "   #", "   #"],
    "5": ["####", "#   ", "#   ", "####", "   #", "   #", "####"],
    "6": ["####", "#   ", "#   ", "####", "#  #", "#  #", "####"],
    "7": ["####", "   #", "   #", "   #", "   #", "   #", "   #"],
    "8": ["####", "#  #", "#  #", "####", "#  #", "#  #", "####"],
    "9": ["####", "#  #", "#  #", "####", "   #", "   #", "####"],
    " ": ["    ", "    ", "    ", "    ", "    ", "    ", "    "],
    "-": ["    ", "    ", "    ", "####", "    ", "    ", "    "],
}
DIGIT_ROWS = 7


def visible_len(s):
    return len(ANSI_RE.sub("", s))


def line(content):
    pad = WIDTH - 2 - visible_len(content)
    return f"|{content}{' ' * max(0, pad)}|"


def hdr(content="", char="="):
    if not content:
        return f"+{char * (WIDTH - 2)}+"
    pad = WIDTH - 2 - visible_len(content)
    left = pad // 2
    right = pad - left
    return f"+{char * left}{content}{char * right}+"


def big(s, color=GB):
    """Genera DIGIT_ROWS filas de strings con dígitos grandes coloreados."""
    rows = ["" for _ in range(DIGIT_ROWS)]
    for i, ch in enumerate(s):
        glyph = DIGITS.get(ch, DIGITS[" "])
        for r in range(DIGIT_ROWS):
            rows[r] += glyph[r]
            if i < len(s) - 1:
                rows[r] += " "
    return [f"{color}{row}{RST}" for row in rows]


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

    # Big digits para SPEED, RPM, GEAR
    speed_str = f"{s['speed']:>3}"
    rpm_str = f"{s['rpm']:>4}"
    gear_str = str(s["gear"]) if s["gear"] else "-"

    speed_big = big(speed_str, GB)              # 4*3 + 2 gaps = 14 cols
    rpm_big = big(rpm_str, rpm_c)               # 4*4 + 3 gaps = 19 cols
    gear_big = big(gear_str, GB)                # 4 cols

    # Combinamos las 7 filas: SPEED ... RPM ... GEAR
    main_rows = []
    for r in range(DIGIT_ROWS):
        sp = speed_big[r]
        rp = rpm_big[r]
        gr = gear_big[r]
        main_rows.append(f"  {sp}    {rp}     {gr}")

    # Barras debajo
    sp_bar = bar(s["speed"], SPEED_MAX, 14)
    rpm_bar = bar(s["rpm"], RPM_MAX, 19, redline=RPM_REDLINE)
    online = f"{G}[ ON ]{RST}" if not s["mock_active"] else f"{A}[MOCK]{RST}"
    mock_str = "1" if s["mock_active"] else "0"

    # Alerts
    alert_line = "[ ALL SYSTEMS NOMINAL ]"
    alert_color = G
    if s.get("alerts"):
        alert_line = "! " + " | ".join(s["alerts"]) + " !"
        alert_color = R

    import datetime
    now = datetime.datetime.now().strftime("%Y-%m-%d  %H:%M:%S")

    lines = [
        CLR + GB + hdr(f" ROBCO INDUSTRIES ") + RST,
        G + line(f"  ROYAL ENFIELD 650  -  INTERCEPTOR DIAGNOSTIC TERMINAL"),
        line(f"  TERMINAL ID: PIP-OS v3.4.1     {now}"),
        hdr(),
        line(""),
        line(f"   {g}SPEED km/h{G}        {g}RPM{G}              {g}GEAR{G}"),
        line(""),
        line(main_rows[0]),
        line(main_rows[1]),
        line(main_rows[2]),
        line(main_rows[3]),
        line(main_rows[4]),
        line(main_rows[5]),
        line(main_rows[6]),
        line(""),
        line(f"   {GB}{sp_bar}{G}    {rpm_c}{rpm_bar}{G}"),
        line(f"   0       100   200    0          redline   max"),
        line(""),
        hdr(),
        line(f"  THROTTLE  {GB}{s['tps']:>3.0f}{G}%   LOAD  {GB}{s['load']:>3}{G}%   L/100km  {GB}{s['fuel_l_100km']:>4.1f}{G}"),
        line(f"  EOT  {eot_c}{s['eot']:>3}C{G} {eot_c}{eot_lbl}{G}    IAT  {GB}{s['iat']:>3}{G}C    BAT  {bat_c}{s['voltage']:>4.1f}V{G} {bat_c}{bat_lbl}{G}"),
        hdr(),
        line(f"  ALERTS:  {alert_color}{alert_line}{G}"),
        hdr(),
        line(f"  TANK SINCE FILL              SESSION"),
        line(f"  - {GB}{s['tank_l']:>5.2f}{G} L / {GB}{s['tank_km']:>5.1f}{G} km     - ELAPSED  {GB}{s['session_min']:>3}{G} min"),
        line(f"  - AVG    {GB}{s['tank_avg']:>4.1f}{G} L/100km     - MAX SPD  {GB}{s['session_vmax']:>3}{G} km/h"),
        line(f"  - COST   {GB}Q{s['tank_cost']:>6.2f}{G}        - MAX RPM  {GB}{s['session_rpmmax']:>4}{G}"),
        hdr(),
        line(f"  > NETWORK   {GB}{s['ssid']}{G} @ {GB}{s['ip']}{G}"),
        line(f"  > MOCK_OBD  {GB}{mock_str}{G}    UPTIME  {GB}{s['uptime']}{G}"),
        line(f"  > MODE      {online}"),
        line(""),
        line(f"  {g}>>> TOUCH SCREEN: NAVIGATION COMING SOON <<<{G}"),
        line(f"  {g}    F2: shell  |  CTRL+C: exit  |  REFRESH 0.5s{G}"),
        GB + hdr(char="=") + RST,
    ]
    return "\n".join(lines) + RST + "\n"


if __name__ == "__main__":
    sys.stdout.write(render(S))
    sys.stdout.flush()
