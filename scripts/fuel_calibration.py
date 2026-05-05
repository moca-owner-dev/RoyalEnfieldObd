#!/usr/bin/env python3
"""Reporte de combustible por ride y calibración del FUEL_CORRECTION_FACTOR.

El backend escribe fuel_lh ya corregido con el factor actual (default 0.36).
Para recalibrar contra un fill-up real, pasa los rides desde el último tanqueo
con --actual-l <litros_cargados> y el script te da el factor sugerido.

Uso:
    python3 scripts/fuel_calibration.py logs/2026-05-05/ride_*.csv
    python3 scripts/fuel_calibration.py logs/2026-04-30/ logs/2026-05-02/ logs/2026-05-05/
    python3 scripts/fuel_calibration.py --actual-l 7.5 --current-factor 0.36 logs/2026-05-*/
"""
import argparse
import csv
import datetime
import sys
from pathlib import Path

DEFAULT_FACTOR = 0.36
TS_FORMATS = ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%H:%M:%S")


def parse_ts(s):
    s = (s or "").strip()
    if not s:
        return None
    for fmt in TS_FORMATS:
        try:
            return datetime.datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def fnum(s, default=0.0):
    try:
        return float(s)
    except (TypeError, ValueError):
        return default


def integrate(path: Path):
    """Devuelve (distance_km, fuel_l_estimated, duration_h, samples_used).

    Integra fuel_lh × dt (litros) y speed × dt (km). dt es el delta entre
    timestamps consecutivos, capado a 5s para no inflar pausas largas.
    """
    with path.open() as f:
        rows = list(csv.DictReader(f))
    if len(rows) < 2:
        return 0.0, 0.0, 0.0, 0

    dist = 0.0
    fuel = 0.0
    dur_h = 0.0
    used = 0

    prev_ts = parse_ts(rows[0].get("timestamp"))
    for r in rows[1:]:
        ts = parse_ts(r.get("timestamp"))
        if ts is None or prev_ts is None:
            prev_ts = ts
            continue
        dt = (ts - prev_ts).total_seconds()
        prev_ts = ts
        if dt <= 0 or dt > 5.0:
            continue
        dt_h = dt / 3600.0
        dist += fnum(r.get("speed")) * dt_h
        fuel += fnum(r.get("fuel_lh")) * dt_h
        dur_h += dt_h
        used += 1

    return dist, fuel, dur_h, used


def is_failed(path: Path):
    """Heurística simple — archivo demasiado pequeño o sin datos."""
    if path.stat().st_size < 200:
        return True
    return False


def fmt_duration(h):
    if h <= 0:
        return "0m"
    total_min = int(round(h * 60))
    if total_min < 60:
        return f"{total_min}m"
    return f"{total_min // 60}h {total_min % 60:02d}m"


def expand_paths(args):
    out = []
    for a in args:
        p = Path(a)
        if p.is_dir():
            out.extend(sorted(p.glob("ride_*.csv")))
        elif p.is_file():
            out.append(p)
    return out


def main():
    ap = argparse.ArgumentParser(description="Reporte de combustible y calibración.")
    ap.add_argument("paths", nargs="+", help="archivos CSV o directorios")
    ap.add_argument("--actual-l", type=float, default=None,
                    help="Litros realmente cargados en el tanque (para calibrar).")
    ap.add_argument("--current-factor", type=float, default=DEFAULT_FACTOR,
                    help=f"Factor de corrección usado al grabar (default {DEFAULT_FACTOR}).")
    ap.add_argument("--min-km", type=float, default=0.5,
                    help="Ignora rides con menos de N km recorridos (default 0.5).")
    args = ap.parse_args()

    paths = expand_paths(args.paths)
    if not paths:
        print("nada para analizar", file=sys.stderr)
        sys.exit(1)

    rows_out = []
    total_km = 0.0
    total_l = 0.0
    total_h = 0.0
    skipped = 0

    for p in paths:
        if is_failed(p):
            skipped += 1
            continue
        dist, fuel, dur_h, used = integrate(p)
        if dist < args.min_km:
            skipped += 1
            continue
        l100 = (fuel / dist * 100.0) if dist > 0 else 0.0
        rows_out.append((p, dist, fuel, dur_h, l100, used))
        total_km += dist
        total_l += fuel
        total_h += dur_h

    if not rows_out:
        print("ningún ride con datos suficientes", file=sys.stderr)
        sys.exit(1)

    # Tabla por ride
    header = f"{'archivo':<40} {'km':>7} {'L est':>7} {'L/100':>7} {'tiempo':>8}"
    print(header)
    print("-" * len(header))
    for p, dist, fuel, dur_h, l100, used in rows_out:
        print(f"{p.name:<40} {dist:>7.2f} {fuel:>7.3f} {l100:>7.2f} {fmt_duration(dur_h):>8}")

    # Total
    print("-" * len(header))
    avg_l100 = (total_l / total_km * 100.0) if total_km > 0 else 0.0
    print(f"{'TOTAL':<40} {total_km:>7.2f} {total_l:>7.3f} {avg_l100:>7.2f} {fmt_duration(total_h):>8}")
    print(f"\nRides con datos: {len(rows_out)}    descartados: {skipped}")
    print(f"Factor de corrección usado al grabar: {args.current_factor}")

    # Calibración
    if args.actual_l is not None:
        if total_l <= 0:
            print("\nNo se puede calibrar: total estimado = 0", file=sys.stderr)
            sys.exit(1)
        ratio = args.actual_l / total_l
        new_factor = args.current_factor * ratio
        real_l100 = args.actual_l / total_km * 100.0
        print()
        print("=" * 60)
        print("  CALIBRACIÓN")
        print("=" * 60)
        print(f"  Litros REALES cargados ........ {args.actual_l:.2f} L")
        print(f"  Litros estimados (suma rides) . {total_l:.3f} L")
        print(f"  Ratio real/estimado ........... {ratio:.4f}")
        print(f"  Factor actual ................. {args.current_factor}")
        print(f"  >> Factor sugerido ............ {new_factor:.4f}")
        print()
        print(f"  Consumo real .................. {real_l100:.2f} L/100km")
        print(f"  Consumo estimado .............. {avg_l100:.2f} L/100km")
        print()
        print(f"  Para aplicar:")
        print(f"    ssh pipboy@10.42.0.249 "
              f"\"sed -i 's/^FUEL_CORRECTION_FACTOR=.*/FUEL_CORRECTION_FACTOR={new_factor:.4f}/' "
              f"~/RoyalEnfieldObd/runtime.env && sudo systemctl restart interceptor\"")


if __name__ == "__main__":
    main()
