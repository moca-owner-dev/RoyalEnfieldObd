<script setup>
import { computed } from 'vue'
import { useObdData } from './composables/useObdData'
import logoLargo from './assets/logo_largo.webp'

const { data, session, tank, healthy, markTankFull } = useObdData(500)

// CALIBRATION FOR J-SERIES 350 (Classic/Bullet)
const SPEED_MAX = 150        // Interceptor was 200
const RPM_MAX = 7000         // Interceptor was 8500
const RPM_REDLINE = 6000     // Interceptor was 7000

const speedPct = computed(() => Math.min(100, (data.value.speed / SPEED_MAX) * 100))
const rpmPct = computed(() => Math.min(100, (data.value.rpm / RPM_MAX) * 100))
const inRedline = computed(() => data.value.rpm >= RPM_REDLINE)

const conn = computed(() => {
  if (!healthy.value) return { label: 'Backend offline', cls: 'is-danger' }
  if (!data.value.connected) {
    const s = data.value.stale_seconds
    if (s != null) return { label: `No data available ${s.toFixed(0)}s`, cls: 'is-warn' }
    return { label: 'Dongle disconnected', cls: 'is-warn' }
  }
  return { label: 'Connected', cls: 'is-ok' }
})

// EOT zonas para color
const eotClass = computed(() => {
  const v = data.value.eot
  if (v < 60) return 'cool'
  if (v <= 105) return 'normal'
  if (v <= 115) return 'warn'
  return 'danger'
})
const voltClass = computed(() => {
  const v = data.value.voltage
  if (!data.value.connected) return 'muted'
  if (v < 12.0) return 'danger'
  if (v < 13.0) return 'warn'
  return 'normal'
})

function fmt(v, digits = 0, dash = '—') {
  if (v == null || isNaN(v)) return dash
  return Number(v).toFixed(digits)
}
</script>

<template>
  <div class="dash">
    <header class="topbar">
      <img :src="logoLargo" alt="Royal Enfield" class="brand" />
      <div class="status" :class="conn.cls">
        <span class="dot" />
        <span class="lbl">{{ conn.label }}</span>
      </div>
    </header>

    <main class="grid" :class="{ stale: !data.connected }">
      <!-- VELOCIDAD: prioridad 1, dominante -->
      <section class="cell speed">
        <div class="micro">Velocity</div>
        <div class="big">
          <span class="num">{{ fmt(data.speed, 0, '0') }}</span>
          <span class="unit">km/h</span>
        </div>
        <div class="bar">
          <div class="fill" :style="{ width: speedPct + '%' }" />
        </div>
        <div class="bar-ticks"><span>0</span><span>75</span><span>150</span></div>
      </section>

      <!-- RPM: prioridad 2 -->
      <section class="cell rpm" :class="{ redline: inRedline }">
        <div class="micro">RPM</div>
        <div class="big">
          <span class="num">{{ fmt(data.rpm, 0, '0') }}</span>
        </div>
        <div class="bar">
          <div class="fill" :style="{ width: rpmPct + '%' }" />
          <div class="redmark" />
        </div>
        <div class="bar-ticks"><span>0</span><span>{{ RPM_REDLINE }}</span><span>{{ RPM_MAX }}</span></div>
      </section>

      <!-- MARCHA: prioridad 3, no invasiva -->
      <section class="cell gear">
        <div class="micro">Gear</div>
        <div class="gear-num">{{ data.gear ?? '–' }}</div>
      </section>
    </main>

    <!-- Strip secundario: temps + voltaje + throttle + carga + L/100km -->
    <section class="strip">
      <div class="metric" :class="eotClass">
        <span class="m-lbl">Oil Temperature</span>
        <span class="m-val">{{ fmt(data.eot, 0) }}<small>°C</small></span>
      </div>
      <div class="metric">
        <span class="m-lbl">Air Temperature</span>
        <span class="m-val">{{ fmt(data.iat, 0) }}<small>°C</small></span>
      </div>
      <div class="metric" :class="voltClass">
        <span class="m-lbl">Battery Voltage</span>
        <span class="m-val">{{ fmt(data.voltage, 1) }}<small>V</small></span>
      </div>
      <div class="metric">
        <span class="m-lbl">Throttle</span>
        <span class="m-val">{{ fmt(data.tps, 0) }}<small>%</small></span>
      </div>
      <div class="metric">
        <span class="m-lbl">Load</span>
        <span class="m-val">{{ fmt(data.load, 0) }}<small>%</small></span>
      </div>
      <div class="metric accent">
        <span class="m-lbl">L/100km</span>
        <span class="m-val">{{ fmt(data.fuel_l_100km, 1) }}</span>
      </div>
    </section>

    <!-- Footer: tanque + sesión -->
    <footer class="foot">
      <button class="tank-btn" @click="markTankFull" title="Marcar tanque lleno">
        ⛽ Tank Full
      </button>
      <div class="tank-info">
        <span><b>{{ fmt(tank.since_fill_l, 2, '0.00') }}</b> L</span>
        <span>·</span>
        <span><b>{{ fmt(tank.since_fill_km, 1, '0') }}</b> km</span>
        <span>·</span>
        <span>Mileage <b>{{ fmt(tank.avg_l_100km, 1) }}</b> L/100km</span>
      </div>
      <div class="session-info">
        <span>Session <b>{{ fmt(session.elapsed_min, 0) }}</b> min</span>
        <span>·</span>
        <span>Vmax <b>{{ fmt(session.v_max, 0) }}</b></span>
      </div>
    </footer>
  </div>
</template>

<style scoped>
.dash {
  display: grid;
  grid-template-rows: auto 1fr auto auto;
  height: 100vh;
  width: 100vw;
  padding: 0.4rem 0.6rem;
  gap: 0.4rem;
  background: var(--c-bg);
}

/* TOPBAR */
.topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 0.2rem;
}
.brand {
  height: 22px;
  width: auto;
}
.status {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.72rem;
  color: var(--c-muted);
  text-transform: uppercase;
  letter-spacing: 0.08em;
}
.dot {
  width: 8px; height: 8px; border-radius: 50%;
  background: var(--c-muted);
}
.status.is-ok .dot { background: var(--c-success); }
.status.is-ok .lbl { color: var(--c-fg); }
.status.is-warn .dot { background: var(--c-warn); }
.status.is-warn .lbl { color: var(--c-warn); }
.status.is-danger .dot { background: var(--c-danger); }
.status.is-danger .lbl { color: var(--c-danger); }

/* MAIN GRID — SPEED dominante, RPM segundo, GEAR pequeño */
.grid {
  display: grid;
  grid-template-columns: 1.6fr 1.2fr 0.8fr;
  gap: 0.5rem;
  min-height: 0;
}
.grid.stale .cell { opacity: 0.55; }

.cell {
  background: var(--c-panel);
  border: 1px solid var(--c-border);
  border-radius: 8px;
  padding: 0.6rem 0.8rem;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.micro {
  font-size: 0.65rem;
  letter-spacing: 0.18em;
  color: var(--c-muted);
  text-transform: uppercase;
  margin-bottom: 0.2rem;
}

.big {
  display: flex;
  align-items: baseline;
  gap: 0.4rem;
  line-height: 0.95;
  margin-bottom: 0.4rem;
}
.big .num {
  font-size: clamp(3.2rem, 11vw, 7rem);
  font-weight: 800;
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.03em;
  color: var(--c-fg);
}
.big .unit {
  font-size: 1rem;
  color: var(--c-muted);
  text-transform: lowercase;
  letter-spacing: 0.05em;
}

/* RPM cell — redline highlight */
.rpm.redline .num { color: var(--c-danger); }
.rpm.redline { border-color: var(--c-danger); box-shadow: 0 0 12px rgba(248, 81, 73, 0.25); }

/* GEAR cell — más chico, centrado */
.gear { align-items: center; justify-content: center; }
.gear .gear-num {
  font-size: clamp(3rem, 9vw, 5.5rem);
  font-weight: 800;
  font-variant-numeric: tabular-nums;
  color: var(--c-info);
  line-height: 1;
}

/* BAR (gauge horizontal) */
.bar {
  position: relative;
  height: 6px;
  background: var(--c-bar-bg);
  border-radius: 3px;
  overflow: hidden;
}
.bar .fill {
  height: 100%;
  background: linear-gradient(90deg, var(--c-success), var(--c-info));
  transition: width 0.2s ease-out;
}
.rpm .bar .fill { background: linear-gradient(90deg, var(--c-info), var(--c-warn), var(--c-danger)); }
.rpm .redmark {
  position: absolute;
  top: 0; bottom: 0;
  left: calc(7000 / 8500 * 100%);
  width: 2px;
  background: var(--c-danger);
}
.bar-ticks {
  display: flex;
  justify-content: space-between;
  font-size: 0.6rem;
  color: var(--c-muted);
  margin-top: 0.15rem;
  font-variant-numeric: tabular-nums;
}

/* STRIP secundario — todo en una fila */
.strip {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 0.4rem;
  padding: 0.1rem 0;
}
.metric {
  background: var(--c-panel);
  border: 1px solid var(--c-border);
  border-radius: 6px;
  padding: 0.35rem 0.5rem;
  display: flex;
  justify-content: space-between;
  align-items: baseline;
}
.m-lbl {
  font-size: 0.6rem;
  color: var(--c-muted);
  letter-spacing: 0.12em;
  text-transform: uppercase;
}
.m-val {
  font-size: 1.05rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}
.m-val small {
  font-size: 0.65rem;
  font-weight: 400;
  color: var(--c-muted);
  margin-left: 0.1rem;
}
.metric.cool .m-val { color: var(--c-info); }
.metric.normal .m-val { color: var(--c-success); }
.metric.warn .m-val { color: var(--c-warn); }
.metric.danger .m-val { color: var(--c-danger); }
.metric.muted .m-val { color: var(--c-muted); }
.metric.accent {
  border-color: var(--c-info);
}
.metric.accent .m-val { color: var(--c-info); }

/* FOOTER (tanque + Session) */
.foot {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  padding: 0.1rem;
  font-size: 0.78rem;
  color: var(--c-muted);
  flex-wrap: wrap;
}
.tank-btn {
  background: var(--c-panel);
  color: var(--c-fg);
  border: 1px solid var(--c-border);
  border-radius: 6px;
  padding: 0.3rem 0.7rem;
  font-size: 0.78rem;
  cursor: pointer;
  white-space: nowrap;
}
.tank-btn:hover { border-color: var(--c-info); color: var(--c-info); }
.tank-btn:active { background: var(--c-info); color: var(--c-bg); }

.tank-info, .session-info {
  display: flex;
  gap: 0.4rem;
  align-items: center;
}
.tank-info b, .session-info b { color: var(--c-fg); font-weight: 700; }
.session-info { margin-left: auto; }
</style>
