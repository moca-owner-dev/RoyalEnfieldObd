"""
Cliente ELM327 + decoders OBD2 + cálculos para Royal Enfield Interceptor 650.

Encapsula la comunicación TCP con el dongle, parsing de PIDs, y los cálculos
derivados (consumo de combustible, marcha estimada).
"""

import os
import socket
import time
import threading
from typing import Optional

# -----------------------------------------------------------------------------
# Configuración
# -----------------------------------------------------------------------------
HOST = "192.168.0.10"
PORT = 35000
TIMEOUT = 2.0  # segundos por query — bajo para detectar drops rápido

# Specs del Interceptor 650 (manual p.4)
DISPLACEMENT_L = 0.648
M_AIR = 28.97              # g/mol masa molar del aire
R_GAS = 8.314              # J/(mol·K) constante de gas ideal
AFR_STOICH = 14.7          # AFR estequiométrico para gasolina
GASOLINE_DENSITY = 745.7   # g/L densidad de gasolina

# Factor de corrección empírico al cálculo speed-density.
# La fórmula raw asume AFR=14.7 (estequio) pero la ECU corre lean (~16-17) en crucero.
# Ajustar contra datos reales de fill-up. Default 0.36 ≈ specs publicados Interceptor 650
# (~4 L/100km vs raw que da ~11 L/100km). Configurable vía env para calibrar fino.
FUEL_CORRECTION_FACTOR = float(os.getenv("FUEL_CORRECTION_FACTOR", "0.36"))

# Transmisión (manual p.4)
GEAR_RATIOS = {1: 2.615, 2: 1.813, 3: 1.429, 4: 1.190, 5: 1.040, 6: 0.962}
PRIMARY_RATIO = 2.05
SECONDARY_RATIO = 2.533
TIRE_CIRCUM_M = 2.008  # 130/70 R18 trasera

# PIDs que vamos a poll en cada ciclo.
# Orden importante: críticos primero para que aparezcan en pantalla más rápido,
# ya que el state se actualiza después de cada query individual.
POLL_PIDS = [
    (0x0C, "rpm"),     # crítico — primero
    (0x0D, "speed"),   # crítico
    (0x11, "tps"),     # importante (afecta cálculo gear)
    (0x0B, "map"),     # importante (afecta cálculo fuel)
    (0x0F, "iat"),     # cambia lento
    (0x5C, "eot"),     # cambia lento
    (0x04, "load"),    # secundario
]


# -----------------------------------------------------------------------------
# Cliente ELM327 (low level)
# -----------------------------------------------------------------------------
class ELM327Client:
    def __init__(self, host: str = HOST, port: int = PORT, timeout: float = TIMEOUT):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.sock: Optional[socket.socket] = None
        self._lock = threading.Lock()

    def connect(self) -> None:
        self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        # Handshake
        self._send("ATZ", wait=1.5)
        self._send("ATE0")
        self._send("ATL0")
        self._send("ATH0")
        self._send("ATS0")
        self._send("ATSP0")
        # Auto-detect activado con primer query
        self._send("0100", wait=8.0)

    def close(self) -> None:
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass
            self.sock = None

    def _drain(self) -> None:
        """Descarta cualquier byte pendiente en el socket (bytes de respuestas
        anteriores que llegaron tarde y quedaron en el kernel buffer).
        Crucial para evitar buffer cross-talk entre queries.
        """
        if self.sock is None:
            return
        self.sock.setblocking(False)
        try:
            while True:
                chunk = self.sock.recv(4096)
                if not chunk:
                    break
        except (BlockingIOError, OSError):
            pass
        finally:
            try:
                self.sock.setblocking(True)
            except OSError:
                pass

    def _send(self, cmd: str, wait: float = 0.05) -> str:
        if self.sock is None:
            raise RuntimeError("ELM327 no conectado")
        with self._lock:
            self._drain()  # limpiar bytes basura de queries previas
            self.sock.sendall((cmd + "\r").encode("ascii"))
            time.sleep(wait)
            buf = b""
            self.sock.settimeout(self.timeout)
            try:
                while True:
                    chunk = self.sock.recv(1024)
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

    def query_pid(self, pid: int) -> Optional[bytes]:
        """Mode 01 query. Devuelve bytes de datos o None."""
        cmd = f"01{pid:02X}"
        resp = self._send(cmd)
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

    def query_voltage(self) -> Optional[float]:
        """ATRV — voltaje de batería visto por el dongle.
        Validación estricta: la respuesta debe terminar en V y estar entre 0-30V.
        Esto evita interpretar bytes basura (e.g. respuestas OBD de PIDs anteriores)
        como voltaje gigante.
        """
        try:
            raw = self._send("ATRV").strip()
            if not raw.endswith("V"):
                return None
            v = float(raw[:-1].strip())
            if 0.0 <= v <= 30.0:
                return v
            return None
        except (ValueError, AttributeError):
            return None


# -----------------------------------------------------------------------------
# Decoders y cálculos
# -----------------------------------------------------------------------------
def decode_pid(pid: int, data: Optional[bytes]) -> Optional[float]:
    if data is None or len(data) == 0:
        return None
    A = data[0]
    B = data[1] if len(data) > 1 else 0
    if pid == 0x04: return A * 100.0 / 255          # engine load %
    if pid == 0x0B: return float(A)                 # MAP kPa
    if pid == 0x0C: return ((A * 256) + B) / 4.0    # RPM
    if pid == 0x0D: return float(A)                 # speed km/h
    if pid == 0x0E: return A / 2.0 - 64             # timing advance °
    if pid == 0x0F: return A - 40.0                 # IAT °C
    if pid == 0x11: return A * 100.0 / 255          # TPS %
    if pid == 0x5C: return A - 40.0                 # EOT °C
    return None


def estimate_gear(rpm: float, speed_kmh: float) -> Optional[int]:
    """Devuelve marcha estimada (1-6) o None si no se puede determinar."""
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


def calc_fuel_lh(map_kpa: float, rpm: float, iat_c: float, ve: float = 0.85) -> float:
    """Speed-density estimate: consumo en L/h.
    Multiplica por FUEL_CORRECTION_FACTOR para compensar la diferencia entre
    AFR estequiométrico (14.7) y AFR lean real de la ECU en crucero (~16-17).
    """
    if rpm < 100 or map_kpa < 1:
        return 0.0
    iat_k = max(iat_c + 273.15, 200.0)
    maf_gs = (map_kpa * DISPLACEMENT_L * rpm * ve * M_AIR) / (R_GAS * iat_k * 120)
    fuel_gs = maf_gs / AFR_STOICH
    return fuel_gs * 3600 / GASOLINE_DENSITY * FUEL_CORRECTION_FACTOR
