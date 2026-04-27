"""
FastAPI server para tablero virtual del Royal Enfield Interceptor 650.

Mantiene un thread de fondo que poll-ea el dongle ELM327 a ~2 Hz y guarda
los valores en memoria. La API expone esos valores como JSON.

Uso:
    cd backend
    uvicorn main:app --reload --port 8000

En producción (sirviendo el dist/ del frontend):
    uvicorn main:app --port 8000
"""

import os
import time
import threading
import csv
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from obd import (
    ELM327Client,
    POLL_PIDS,
    decode_pid,
    estimate_gear,
    calc_fuel_lh,
)

# -----------------------------------------------------------------------------
# Estado global compartido
# -----------------------------------------------------------------------------
_state_lock = threading.Lock()
_state = {
    "connected": False,
    "last_update": None,
    "rpm": 0.0,
    "speed": 0.0,
    "tps": 0.0,
    "map": 0.0,
    "iat": 25.0,
    "eot": 0.0,
    "load": 0.0,
    "voltage": 0.0,
    "fuel_lh": 0.0,
    "gear": None,
}

_session = {
    "start": time.time(),
    "v_max": 0.0,
    "rpm_max": 0.0,
    "eot_max": 0.0,
    "fuel_total_l": 0.0,
    "_last_t": time.time(),
}

_poll_thread: Optional[threading.Thread] = None
_stop_event = threading.Event()
_csv_writer = None
_csv_file = None

# Configurables vía env
VE = float(os.getenv("VE", "0.85"))
POLL_INTERVAL = float(os.getenv("POLL_INTERVAL", "0.5"))
LOG_DIR = Path(os.getenv("LOG_DIR", "../logs"))
STALE_AFTER_SECONDS = 2.0  # si no llegan datos nuevos en 2s, marcamos disconnected


# -----------------------------------------------------------------------------
# Background poller
# -----------------------------------------------------------------------------
def _poll_loop():
    global _csv_writer, _csv_file
    client = ELM327Client()
    backoff = 1.0

    # Setup CSV log
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / f"ride_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    _csv_file = open(log_path, "w", newline="")
    _csv_writer = csv.writer(_csv_file)
    _csv_writer.writerow([
        "timestamp", "rpm", "speed", "tps", "map", "iat", "eot",
        "load", "voltage", "fuel_lh", "gear",
    ])
    print(f"[poller] CSV log: {log_path.resolve()}")

    while not _stop_event.is_set():
        # Reconnect loop
        if client.sock is None:
            try:
                print(f"[poller] conectando a ELM327...")
                client.connect()
                with _state_lock:
                    _state["connected"] = True
                backoff = 1.0
                print("[poller] OK conectado")
            except OSError as e:
                with _state_lock:
                    _state["connected"] = False
                print(f"[poller] no se pudo conectar ({e}); retry en {backoff}s")
                _stop_event.wait(backoff)
                backoff = min(backoff * 2, 30.0)
                continue

        # Poll cycle: update state después de cada PID individual
        # para que datos críticos (RPM/speed) aparezcan ASAP en el frontend
        t0 = time.time()
        try:
            for pid, name in POLL_PIDS:
                v = decode_pid(pid, client.query_pid(pid))
                if v is not None:
                    now = time.time()
                    with _state_lock:
                        _state[name] = v
                        _state["last_update"] = now
                        _state["connected"] = True
                        # Recalcular derived al toque para que se vean fluidos
                        _state["fuel_lh"] = calc_fuel_lh(
                            _state["map"], _state["rpm"], _state["iat"], VE,
                        )
                        _state["gear"] = estimate_gear(_state["rpm"], _state["speed"])
                        # Sesión incremental
                        dt_h = (now - _session["_last_t"]) / 3600
                        _session["v_max"] = max(_session["v_max"], _state["speed"])
                        _session["rpm_max"] = max(_session["rpm_max"], _state["rpm"])
                        _session["eot_max"] = max(_session["eot_max"], _state["eot"])
                        _session["fuel_total_l"] += _state["fuel_lh"] * dt_h
                        _session["_last_t"] = now

            volt = client.query_voltage()
            if volt is not None:
                with _state_lock:
                    _state["voltage"] = volt
                    _state["last_update"] = time.time()
        except OSError as e:
            print(f"[poller] error de socket: {e}; reconnect")
            client.close()
            with _state_lock:
                _state["connected"] = False
            continue

        # CSV row al final del ciclo (un row por ciclo completo)
        ts = datetime.now().strftime("%H:%M:%S")
        with _state_lock:
            row = [
                ts, f"{_state['rpm']:.0f}", f"{_state['speed']:.0f}",
                f"{_state['tps']:.2f}", f"{_state['map']:.1f}",
                f"{_state['iat']:.1f}", f"{_state['eot']:.1f}",
                f"{_state['load']:.2f}", f"{_state['voltage']:.2f}",
                f"{_state['fuel_lh']:.3f}", _state["gear"] or "",
            ]
        _csv_writer.writerow(row)
        _csv_file.flush()

        # Mantener intervalo
        elapsed = time.time() - t0
        if elapsed < POLL_INTERVAL:
            _stop_event.wait(POLL_INTERVAL - elapsed)

    client.close()
    if _csv_file:
        _csv_file.close()
    print("[poller] terminado")


# -----------------------------------------------------------------------------
# FastAPI app
# -----------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _poll_thread
    _poll_thread = threading.Thread(target=_poll_loop, daemon=True)
    _poll_thread.start()
    yield
    _stop_event.set()
    if _poll_thread:
        _poll_thread.join(timeout=2.0)


app = FastAPI(title="RE 650 Dashboard", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _is_fresh(last_update):
    """Devuelve True si last_update es lo suficientemente reciente."""
    if last_update is None:
        return False
    return (time.time() - last_update) < STALE_AFTER_SECONDS


@app.get("/api/health")
def health():
    with _state_lock:
        last = _state["last_update"]
        return {
            "connected": _state["connected"] and _is_fresh(last),
            "last_update": last,
            "stale_seconds": (time.time() - last) if last else None,
            "now": time.time(),
        }


@app.get("/api/data")
def get_data():
    with _state_lock:
        snap = dict(_state)
    # connected efectivo: depende de freshness, no solo del último estado del socket
    snap["connected"] = snap["connected"] and _is_fresh(snap["last_update"])
    snap["stale_seconds"] = (
        round(time.time() - snap["last_update"], 2) if snap["last_update"] else None
    )
    return snap


@app.get("/api/session")
def get_session():
    with _state_lock:
        elapsed_min = (time.time() - _session["start"]) / 60
        return {
            "elapsed_min": round(elapsed_min, 2),
            "v_max": _session["v_max"],
            "rpm_max": _session["rpm_max"],
            "eot_max": _session["eot_max"],
            "fuel_total_l": round(_session["fuel_total_l"], 3),
        }


@app.post("/api/session/reset")
def reset_session():
    with _state_lock:
        now = time.time()
        _session["start"] = now
        _session["_last_t"] = now
        _session["v_max"] = 0.0
        _session["rpm_max"] = 0.0
        _session["eot_max"] = 0.0
        _session["fuel_total_l"] = 0.0
    return {"ok": True}


# -----------------------------------------------------------------------------
# Servir el frontend buildeado en producción
# (en dev, Vite se encarga; esto sólo se activa si existe el build)
# -----------------------------------------------------------------------------
DIST_DIR = Path(__file__).parent.parent / "frontend" / "dist"
if DIST_DIR.exists():
    app.mount("/assets", StaticFiles(directory=DIST_DIR / "assets"), name="assets")

    @app.get("/")
    def root_index():
        return FileResponse(DIST_DIR / "index.html")
else:
    @app.get("/")
    def root_dev():
        return JSONResponse({
            "msg": "Dev mode: corré `npm run dev` en frontend/ y abrí http://localhost:5173",
            "api_endpoints": ["/api/data", "/api/session", "/api/health"],
        })
