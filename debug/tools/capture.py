#!/usr/bin/env python3
"""
Captura snapshots del backend a un JSONL para usar como dataset de simulación.

Uso:
    python3 tools/capture.py                      # 180s a 5 Hz
    python3 tools/capture.py --duration 300       # 5 min
    python3 tools/capture.py --rate 10            # 10 Hz (muestreo más fino)
    python3 tools/capture.py --out custom.jsonl   # nombre custom

Cada línea del JSONL es un snapshot completo de /api/data + un timestamp
relativo al inicio de la captura (en segundos).
"""

import json
import time
import urllib.request
import argparse
import sys
from datetime import datetime
from pathlib import Path

API = "http://127.0.0.1:8000/api/data"


def fetch():
    with urllib.request.urlopen(API, timeout=2) as r:
        return json.loads(r.read())


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--duration", type=int, default=180, help="segundos de captura")
    p.add_argument("--rate", type=float, default=5.0, help="Hz de muestreo")
    p.add_argument("--out", help="archivo .jsonl de salida")
    args = p.parse_args()

    if not args.out:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        args.out = f"mock_data/session_{ts}.jsonl"

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    interval = 1.0 / args.rate
    n_total = int(args.duration * args.rate)
    print(f"Captura → {out_path}")
    print(f"Duración: {args.duration}s a {args.rate} Hz = {n_total} samples")
    print(f"Empieza en 3... 2... 1... ¡GO!")
    time.sleep(3)

    t_start = time.time()
    last_progress = t_start
    n_ok = 0
    n_err = 0
    last_rpm_seen = 0
    max_rpm = 0
    max_speed = 0

    with open(out_path, "w") as f:
        try:
            while True:
                t_now = time.time()
                t_rel = t_now - t_start
                if t_rel >= args.duration:
                    break

                try:
                    d = fetch()
                    d["_t_capture"] = round(t_rel, 3)
                    d["_iso"] = datetime.now().isoformat(timespec="milliseconds")
                    f.write(json.dumps(d) + "\n")
                    f.flush()
                    n_ok += 1
                    rpm = d.get("rpm", 0) or 0
                    speed = d.get("speed", 0) or 0
                    if rpm > max_rpm:
                        max_rpm = rpm
                    if speed > max_speed:
                        max_speed = speed
                    last_rpm_seen = rpm
                except Exception as e:
                    n_err += 1
                    if n_err <= 3:
                        print(f"[err] {e}", file=sys.stderr)

                # Progreso cada 15s
                if t_now - last_progress >= 15:
                    pct = int((t_rel / args.duration) * 100)
                    print(f"  [{pct:>3}%] {t_rel:>5.1f}s | {n_ok} samples "
                          f"| rpm_max={max_rpm:.0f} v_max={max_speed:.0f} km/h "
                          f"| ahora rpm={last_rpm_seen:.0f}")
                    last_progress = t_now

                # Mantener cadencia
                next_t = t_start + (n_ok + n_err) * interval
                sleep_for = next_t - time.time()
                if sleep_for > 0:
                    time.sleep(sleep_for)

        except KeyboardInterrupt:
            print("\n[ctrl-c] capturando lo que hay y saliendo...")

    elapsed = time.time() - t_start
    print(f"\n✓ Listo. {n_ok} samples ({n_err} errores) en {elapsed:.1f}s")
    print(f"  Vmax: {max_speed:.0f} km/h, RPMmax: {max_rpm:.0f}")
    print(f"  Archivo: {out_path.resolve()} ({out_path.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
