#!/usr/bin/env python3
"""Pip-Boy SYSTEM STATUS MONITOR para Royal Enfield Interceptor.

Pantalla de estado del sistema (NO el tablero completo): servicios, OBD link,
red, sistema, y al final el estado inicial de la moto. Reintenta hasta que el
API reporte que la ECU está conectada.

Diseñado para 60 cols x 40 rows (LCD 480x320 con VGA8x8).

Para verlo en el LCD del Pi:
    sudo ~/RoyalEnfieldObd/scripts/show-status.sh
"""
import datetime
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.request

# ─── Pip-Boy palette ───
G   = "\033[40;1;32m"   # green bold
GB  = "\033[40;1;92m"   # bright green bold (numbers)
g   = "\033[40;32m"     # green dim
R   = "\033[40;1;91m"   # red
A   = "\033[40;1;93m"   # yellow
RST = "\033[0m"
CLR = "\033[40m\033[2J\033[H"

WIDTH = 60
API_BASE = "http://127.0.0.1:8000"
DONGLE_HOST = "192.168.0.10"
DONGLE_PORT = 35000
REFRESH_SEC = 2.0

ANSI_RE = re.compile(r"\033\[[0-9;]*m")

# 3-row, 4-col ASCII font for big numerals in BIKE STATUS.
DIGIT_FONT = {
    "0": [" __ ", "|  |", "|__|"],
    "1": ["    ", "  / ", " /  "],
    "2": [" __ ", " __|", "|__ "],
    "3": [" __ ", " __|", " __|"],
    "4": ["    ", "|__|", "   |"],
    "5": [" __ ", "|__ ", " __|"],
    "6": [" __ ", "|__ ", "|__|"],
    "7": [" __ ", "   |", "   |"],
    "8": [" __ ", "|__|", "|__|"],
    "9": [" __ ", "|__|", " __|"],
    "-": ["    ", " __ ", "    "],
    " ": ["    ", "    ", "    "],
}


def big_row(value: str, width: int, row: int) -> str:
    """One of three ASCII rows for `value` right-padded to `width` characters."""
    padded = value.rjust(width)
    return "".join(DIGIT_FONT.get(c, DIGIT_FONT[" "])[row] + " " for c in padded)


def visible_len(s):
    return len(ANSI_RE.sub("", s))


def line(content=""):
    pad = WIDTH - 2 - visible_len(content)
    return f"{G}|{content}{' ' * max(0, pad)}|{RST}"


def hdr(content="", char="="):
    if not content:
        return f"{G}+{char * (WIDTH - 2)}+{RST}"
    # Pad the title with spaces so the embedded label is readable.
    label = f" {content.strip()} "
    pad = WIDTH - 2 - visible_len(label)
    left = pad // 2
    right = pad - left
    return f"{G}+{char * left}{label}{char * right}+{RST}"


def section_break():
    return [hdr(), line()]


# ─── Data collectors ───

def sh(cmd, timeout=2):
    try:
        out = subprocess.run(cmd, shell=True, capture_output=True,
                             text=True, timeout=timeout)
        return out.stdout.strip()
    except Exception:
        return ""


def get_api_health():
    try:
        with urllib.request.urlopen(f"{API_BASE}/api/health", timeout=1.0) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


def get_api_data():
    try:
        with urllib.request.urlopen(f"{API_BASE}/api/data", timeout=1.0) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


def get_service_active(name):
    return sh(f"systemctl is-active {name}") == "active"


def get_mock_mode():
    env_path = os.path.expanduser("~/RoyalEnfieldObd/runtime.env")
    try:
        with open(env_path) as f:
            for ln in f:
                if ln.startswith("MOCK_OBD="):
                    return ln.split("=", 1)[1].strip() == "1"
    except Exception:
        pass
    return False


def get_dongle_reachable():
    try:
        with socket.create_connection((DONGLE_HOST, DONGLE_PORT), timeout=0.5):
            return True
    except Exception:
        return False


def get_iface_ip(iface):
    out = sh(f"ip -4 -o addr show dev {iface} 2>/dev/null")
    m = re.search(r"inet (\d+\.\d+\.\d+\.\d+)", out)
    return m.group(1) if m else None


def get_wifi_ssid(iface):
    out = sh(f"iw dev {iface} link 2>/dev/null")
    m = re.search(r"SSID:\s*(.+)", out)
    return m.group(1).strip() if m else None


def get_ap_clients(iface):
    out = sh(f"iw dev {iface} station dump 2>/dev/null")
    return out.count("Station ")


def get_cpu_temp():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            return int(f.read().strip()) / 1000.0
    except Exception:
        return None


def get_loadavg():
    try:
        return os.getloadavg()
    except Exception:
        return (0, 0, 0)


def get_mem():
    try:
        with open("/proc/meminfo") as f:
            info = {}
            for ln in f:
                k, _, v = ln.partition(":")
                info[k] = int(v.strip().split()[0])
        total_mb = info["MemTotal"] // 1024
        avail_mb = info.get("MemAvailable", info.get("MemFree", 0)) // 1024
        used_mb = total_mb - avail_mb
        return used_mb, total_mb
    except Exception:
        return 0, 0


def get_disk_free():
    out = sh("df -h --output=avail / | tail -1").strip()
    return out or "?"


def get_logs_summary():
    logs_dir = os.path.expanduser("~/RoyalEnfieldObd/logs")
    csvs = sh(f"find {logs_dir} -name '*.csv' 2>/dev/null | wc -l")
    size = sh(f"du -sh {logs_dir} 2>/dev/null | cut -f1") or "0"
    return csvs or "0", size


def get_uptime():
    try:
        with open("/proc/uptime") as f:
            secs = float(f.read().split()[0])
        d = int(secs // 86400)
        h = int((secs % 86400) // 3600)
        m = int((secs % 3600) // 60)
        return f"{d}d {h:02d}h {m:02d}m"
    except Exception:
        return "?"


# ─── Render ───

def tag(ok, label_ok="ACTIVE", label_bad="DOWN", color_ok=G, color_bad=R):
    if ok is None:
        return f"{A}[ ?? ]{G}"
    return f"{color_ok}[ {label_ok} ]{G}" if ok else f"{color_bad}[ {label_bad} ]{G}"


def render(state, retry_count):
    api_ok      = state["api_health"] is not None
    svc_ok      = state["svc_active"]
    mock_on     = state["mock_mode"]
    dongle_ok   = state["dongle_reachable"]
    health      = state["api_health"] or {}
    data        = state["api_data"] or {}
    ecu_conn    = bool(health.get("connected"))
    stale       = health.get("stale_seconds")
    last_upd    = health.get("last_update")

    cpu_temp = state["cpu_temp"]
    la1, la5, la15 = state["loadavg"]
    mem_used, mem_total = state["mem"]
    disk = state["disk"]
    csvs, logs_size = state["logs"]

    wlan0_ip = state["wlan0_ip"] or "---"
    wlan1_ip = state["wlan1_ip"] or "---"
    eth_ip   = state["eth_ip"] or "---"
    wlan0_ssid = state["wlan0_ssid"] or "---"
    wlan1_ssid = state["wlan1_ssid"] or "---"
    ap_clients = state["ap_clients"]

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    uptime = state["uptime"]

    # Tags
    svc_tag    = tag(svc_ok, "ACTIVE", "DEAD")
    api_tag    = tag(api_ok, "ONLINE", "DOWN")
    mock_tag   = (f"{A}[  ON   ]{G}" if mock_on else f"{G}[  OFF  ]{G}")
    dongle_tag = tag(dongle_ok, "  UP  ", " DOWN ")

    # CPU temp color
    if cpu_temp is None:
        cpu_str = f"{A}--C{G}"
    elif cpu_temp >= 75:
        cpu_str = f"{R}{cpu_temp:>4.1f}C{G}"
    elif cpu_temp >= 65:
        cpu_str = f"{A}{cpu_temp:>4.1f}C{G}"
    else:
        cpu_str = f"{GB}{cpu_temp:>4.1f}C{G}"

    # OBD link details
    if ecu_conn:
        ecu_tag = f"{G}[CONNECTED]{G}"
    elif api_ok:
        ecu_tag = f"{A}[ WAITING ]{G}"
    else:
        ecu_tag = f"{R}[   ??    ]{G}"

    last_str = "never"
    age_str = "---"
    if last_upd:
        last_str = datetime.datetime.fromtimestamp(last_upd).strftime("%H:%M:%S")
    if stale is not None:
        age_str = f"{stale:.1f}s"

    # Bike readings (big digits + secondary line)
    if ecu_conn and data:
        rpm = data.get("rpm") or 0
        spd = data.get("speed") or 0
        gear = data.get("gear")
        gear_s = str(gear) if gear else "-"
        eot = data.get("eot") or 0
        bat = data.get("voltage") or 0
        tps = data.get("tps") or 0
        spd_str = f"{int(spd):>3d}"
        rpm_str = f"{int(rpm):>4d}"
        gear_str = gear_s
        rpm_color = R if rpm >= 7000 else GB
        bike_secondary = (f"  EOT {GB}{eot:>3.0f}{G}C    "
                          f"BAT {GB}{bat:>4.1f}{G}V    "
                          f"THR {GB}{tps:>3.0f}{G}%    "
                          f"LAST {GB}{last_str}{G}")
        bike_status_msg = f"{G}[ ECU ONLINE - LIVE READINGS ]{G}"
    else:
        spd_str = "---"
        rpm_str = "----"
        gear_str = "-"
        rpm_color = g
        retry_s = f"retry {retry_count}"
        if not api_ok:
            reason = "api off"
        elif not dongle_ok:
            reason = "no dongle"
        elif mock_on:
            reason = "mock"
        else:
            reason = "key off"
        bike_secondary = f"  {ecu_tag}  ({retry_s})  awaiting: {reason}"
        bike_status_msg = f"{A}[ WAITING FOR BIKE ]{G}"

    # Build the 3-row big-digit block for SPD / RPM / GEAR.
    big_lines = []
    for r in range(3):
        spd_part = f"{GB}{big_row(spd_str, 3, r)}{G}"
        rpm_part = f"{rpm_color}{big_row(rpm_str, 4, r)}{G}"
        gear_part = f"{GB}{big_row(gear_str, 1, r)}{G}"
        # 3 sp + SPD(15) + 6 sp + RPM(20) + 6 sp + GEAR(5) + 3 sp = 58 inner cols
        big_lines.append(f"   {spd_part}      {rpm_part}      {gear_part}   ")

    bike_label_row = ("       SPD"
                      "                     RPM"
                      "                  GEAR")
    bike_unit_row  = ("       km/h"
                      "                  / 8500"
                      "                      ")

    # Global status
    if ecu_conn:
        global_msg = f"{G}[ ALL SYSTEMS NOMINAL ]{G}"
    elif api_ok and svc_ok:
        global_msg = f"{A}[ SYS OK - WAITING FOR BIKE ]{G}"
    else:
        global_msg = f"{R}[ DEGRADED ]{G}"

    def section(title, content_lines):
        # Blank lines above and below content inside each box. The top
        # border doubles as the prior section's bottom; a single closing
        # border is appended once at the very end.
        return [hdr(f" {title} "), line(), *content_lines, line()]

    lines = [
        *section("ROBCO INDUSTRIES", [
            line(f"  PIP-OS v3.4.1   {now}   UP {GB}{uptime}{G}"),
        ]),
        *section("BIKE STATUS", [
            line(bike_label_row),
            line(),
            line(big_lines[0]),
            line(big_lines[1]),
            line(big_lines[2]),
            line(),
            line(bike_unit_row),
            line(),
            line(bike_secondary),
        ]),
        *section("NETWORK", [
            line(f"  > wlan0  {GB}{wlan0_ssid:<16}{G} {GB}{wlan0_ip}{G}"),
            line(),
            line(f"  > wlan1  {GB}{wlan1_ssid:<16}{G} {GB}{wlan1_ip}{G}"),
            line(),
            line(f"  > eth0   {' ' * 17}{GB}{eth_ip}{G}"),
            line(),
            line(f"  > AP CLIENTS .................. {GB}{ap_clients}{G}"),
        ]),
        *section("OBD LINK", [
            line(f"  > DONGLE {GB}{DONGLE_HOST}{G}:{GB}{DONGLE_PORT}{G} ..... {dongle_tag}"),
            line(),
            line(f"  > AGE {GB}{age_str}{G}    LAST POLL {GB}{last_str}{G}"),
        ]),
        *section("STATUS", [
            line(f"  {bike_status_msg}"),
        ]),
        hdr(char="="),
    ]
    return CLR + "\n".join(lines) + RST + "\n"


def collect():
    return {
        "api_health":       get_api_health(),
        "api_data":         get_api_data(),
        "svc_active":       get_service_active("interceptor.service"),
        "mock_mode":        get_mock_mode(),
        "dongle_reachable": get_dongle_reachable(),
        "wlan0_ip":         get_iface_ip("wlan0"),
        "wlan1_ip":         get_iface_ip("wlan1"),
        "eth_ip":           get_iface_ip("eth0"),
        "wlan0_ssid":       get_wifi_ssid("wlan0"),
        "wlan1_ssid":       get_wifi_ssid("wlan1"),
        "ap_clients":       get_ap_clients("wlan1"),
        "cpu_temp":         get_cpu_temp(),
        "loadavg":          get_loadavg(),
        "mem":              get_mem(),
        "disk":             get_disk_free(),
        "logs":             get_logs_summary(),
        "uptime":           get_uptime(),
    }


def main():
    retry = 0
    try:
        while True:
            state = collect()
            connected = bool((state["api_health"] or {}).get("connected"))
            if not connected:
                retry += 1
            sys.stdout.write(render(state, retry))
            sys.stdout.flush()
            time.sleep(REFRESH_SEC)
    except KeyboardInterrupt:
        sys.stdout.write(RST + "\n")


if __name__ == "__main__":
    main()
