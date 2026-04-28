#!/usr/bin/env python3
"""Analiza uno o más logs CSV de ride generados por el backend.

Uso:
  python3 scripts/analyze_ride.py logs/2026-04-28/ride_*.csv
  python3 scripts/analyze_ride.py logs/2026-04-28/
  python3 scripts/analyze_ride.py logs/2026-04-27/ride_A.csv logs/2026-04-28/ride_B.csv
"""
import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

CHANNELS = ["rpm", "speed", "tps", "map", "iat", "eot", "load", "voltage", "fuel_lh"]


def load(path: Path):
    with path.open() as f:
        return list(csv.DictReader(f))


def stats(rows, name):
    """Devuelve (min, max, avg, n_nonzero, n_total) ignorando ceros, vacíos y None."""
    vals = []
    for r in rows:
        v = r.get(name)
        if v is None or v in ("", "0", "0.0"):
            continue
        try:
            vals.append(float(v))
        except (ValueError, TypeError):
            pass
    if not vals:
        return None
    return min(vals), max(vals), sum(vals) / len(vals), len(vals), len(rows)


def is_failed(rows):
    """True si el ride es un arranque fallido (RPM siempre 0/None)."""
    return all(r.get("rpm") in (None, "", "0", "0.0") for r in rows)


def frozen_tail(rows, window=50, threshold=20):
    """Cuántos de los últimos `window` samples tienen los mismos rpm+speed."""
    if len(rows) < window:
        window = len(rows)
    last = rows[-1]
    same = sum(1 for r in rows[-window:]
               if r.get("rpm") == last.get("rpm") and r.get("speed") == last.get("speed"))
    return same if same >= threshold else 0


def fmt_stat(s):
    if s is None:
        return "todos cero/vacíos"
    mn, mx, avg, nz, total = s
    pct = nz / total * 100
    return f"min={mn:.1f}  max={mx:.1f}  avg={avg:.1f}  ({pct:.0f}% no-cero)"


def analyze_one(path: Path):
    rows = load(path)
    if not rows:
        print(f"\n  {path.name}: VACÍO\n")
        return None

    print(f"\n{'=' * 64}")
    print(f"  {path.name}")
    print(f"{'=' * 64}")
    t0 = (rows[0].get("timestamp") or "?").strip()
    t1 = (rows[-1].get("timestamp") or "?").strip()
    print(f"  Samples : {len(rows)}")
    print(f"  Tiempo  : {t0}  →  {t1}")

    if is_failed(rows):
        print(f"  >> ride FALLIDO: poller nunca obtuvo data real del ELM327")
        return rows

    print("\n  Stats:")
    for c in CHANNELS:
        print(f"    {c:8} → {fmt_stat(stats(rows, c))}")

    gears = Counter(r["gear"] for r in rows if r["gear"])
    if gears:
        print(f"\n  Marchas: {dict(sorted(gears.items()))}")

    fz = frozen_tail(rows)
    if fz:
        print(f"\n  AVISO cola congelada: últimos {fz}/50 samples idénticos (estado stale post-apagado)")

    return rows


def compare_table(results):
    """results = list of (path, rows) for non-failed rides."""
    if len(results) < 2:
        return
    print(f"\n{'=' * 64}")
    print("  Comparación")
    print(f"{'=' * 64}")
    header = f"  {'archivo':<32} {'samples':>8} {'RPMmax':>7} {'SPDmax':>7} {'EOTmax':>7}"
    print(header)
    print("  " + "-" * (len(header) - 2))
    for path, rows in results:
        rpm_s = stats(rows, "rpm")
        spd_s = stats(rows, "speed")
        eot_s = stats(rows, "eot")
        rpm_max = f"{rpm_s[1]:.0f}" if rpm_s else "-"
        spd_max = f"{spd_s[1]:.0f}" if spd_s else "-"
        eot_max = f"{eot_s[1]:.0f}" if eot_s else "-"
        print(f"  {path.name:<32} {len(rows):>8} {rpm_max:>7} {spd_max:>7} {eot_max:>7}")


def expand_args(args):
    paths = []
    for a in args:
        p = Path(a)
        if p.is_dir():
            paths.extend(sorted(p.glob("ride_*.csv")))
        elif p.is_file():
            paths.append(p)
        else:
            print(f"AVISO: {a} no existe, saltando", file=sys.stderr)
    return paths


def main():
    ap = argparse.ArgumentParser(description="Analiza CSVs de ride.")
    ap.add_argument("paths", nargs="+", help="archivos CSV o directorios")
    args = ap.parse_args()

    paths = expand_args(args.paths)
    if not paths:
        print("nada para analizar", file=sys.stderr)
        sys.exit(1)

    results = []
    for p in paths:
        rows = analyze_one(p)
        if rows is not None and not is_failed(rows):
            results.append((p, rows))

    compare_table(results)


if __name__ == "__main__":
    main()
