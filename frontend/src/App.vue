<script setup>
import { computed } from 'vue'
import { useObdData } from './composables/useObdData'
import Speedometer from './components/Speedometer.vue'
import Tachometer from './components/Tachometer.vue'
import GearDisplay from './components/GearDisplay.vue'
import TempGauge from './components/TempGauge.vue'
import VoltageIndicator from './components/VoltageIndicator.vue'
import AlertsPanel from './components/AlertsPanel.vue'
import SessionStats from './components/SessionStats.vue'

const { data, session, healthy, resetSession } = useObdData(500)

const connectionState = computed(() => {
  if (!healthy.value) return { label: 'Backend offline', color: 'var(--c-danger)' }
  if (!data.value.connected) {
    const stale = data.value.stale_seconds
    if (stale !== null && stale !== undefined) {
      return { label: `Sin datos hace ${stale.toFixed(0)}s`, color: 'var(--c-warn)' }
    }
    return { label: 'Dongle desconectado', color: 'var(--c-warn)' }
  }
  return { label: 'Conectado', color: 'var(--c-success)' }
})
</script>

<template>
  <div class="app">
    <header class="topbar">
      <div class="brand">
        <img src="/logo_largo.webp" alt="Royal Enfield" class="brand-logo" />
      </div>
      <div class="status">
        <span class="dot" :style="{ background: connectionState.color }" />
        {{ connectionState.label }}
      </div>
    </header>

    <main class="grid" :class="{ 'is-stale': !data.connected }">
      <!-- Fila 1: gauges principales -->
      <div class="cell speedometer"><Speedometer :speed="data.speed" /></div>
      <div class="cell gear"><GearDisplay :gear="data.gear" :speed="data.speed" :rpm="data.rpm" /></div>
      <div class="cell tachometer"><Tachometer :rpm="data.rpm" /></div>

      <!-- Fila 2: motor / temp / voltaje -->
      <div class="cell">
        <TempGauge label="ACEITE (EOT)" :value="data.eot" :max="140"
                   :cold="60" :normal="105" :warning="115" :danger="125" />
      </div>
      <div class="cell">
        <TempGauge label="AIRE (IAT)" :value="data.iat" :max="60"
                   :cold="0" :normal="40" :warning="50" :danger="60" />
      </div>
      <div class="cell">
        <VoltageIndicator :voltage="data.voltage" :rpm="data.rpm" />
      </div>

      <!-- Fila 3: throttle/load/MAP en grid pequeño -->
      <div class="cell strip">
        <div class="strip-item">
          <div class="strip-label">THROTTLE</div>
          <div class="strip-val">{{ data.tps.toFixed(1) }}<span>%</span></div>
        </div>
        <div class="strip-item">
          <div class="strip-label">CARGA</div>
          <div class="strip-val">{{ data.load.toFixed(0) }}<span>%</span></div>
        </div>
        <div class="strip-item">
          <div class="strip-label">MAP</div>
          <div class="strip-val">{{ data.map.toFixed(0) }}<span>kPa</span></div>
        </div>
      </div>

      <!-- Fila 4: sesión + alertas -->
      <div class="cell session-cell">
        <SessionStats :session="session" :data="data" @reset="resetSession" />
      </div>
      <div class="cell alerts-cell">
        <AlertsPanel :data="data" />
      </div>
    </main>

    <footer class="footer">
      Last update: {{ data.last_update ? new Date(data.last_update * 1000).toLocaleTimeString() : '—' }}
    </footer>
  </div>
</template>

<style scoped>
.app {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--c-bg);
  color: var(--c-fg);
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
}
.topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 2rem;
  border-bottom: 1px solid var(--c-border);
}
.brand {
  display: flex;
  align-items: center;
}
.brand-logo {
  height: 32px;
  width: auto;
  display: block;
}
.status {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.85rem;
  color: var(--c-muted);
}
.dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.grid {
  flex: 1;
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  grid-template-rows: auto auto auto auto;
  gap: 1rem;
  padding: 1rem 2rem;
  transition: opacity 0.3s, filter 0.3s;
}
/* Cuando no hay datos frescos: atenuar contenido para que se note
   que NO es info en vivo. El header queda vivo para mostrar el estado. */
.grid.is-stale {
  opacity: 0.4;
  filter: grayscale(0.6);
  pointer-events: none;  /* evita interacciones accidentales con datos viejos */
}
.cell {
  display: flex;
  flex-direction: column;
}
.cell > * { flex: 1; }

/* Disposición específica */
.speedometer { grid-column: 1; grid-row: 1; }
.gear        { grid-column: 2; grid-row: 1; }
.tachometer  { grid-column: 3; grid-row: 1; }
.session-cell { grid-column: 1 / 3; }
.alerts-cell  { grid-column: 3; }

/* Strip de throttle/load/map */
.strip {
  grid-column: 1 / 4;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1rem;
  background: var(--c-panel);
  border-radius: 10px;
  padding: 0.8rem 1.2rem;
  border: 1px solid var(--c-border);
}
.strip-item {
  display: flex;
  flex-direction: column;
  align-items: center;
}
.strip-label {
  font-size: 0.7rem;
  color: var(--c-muted);
  letter-spacing: 0.12em;
}
.strip-val {
  font-size: 1.6rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  margin-top: 0.2rem;
}
.strip-val span {
  font-size: 0.8rem;
  color: var(--c-muted);
  margin-left: 0.2rem;
  font-weight: 400;
}

.footer {
  padding: 0.5rem 2rem;
  font-size: 0.7rem;
  color: var(--c-muted);
  text-align: right;
  border-top: 1px solid var(--c-border);
}

/* Responsive: una columna en celular */
@media (max-width: 720px) {
  .grid { grid-template-columns: 1fr; }
  .speedometer, .gear, .tachometer,
  .session-cell, .alerts-cell, .strip {
    grid-column: 1;
  }
  .strip { grid-template-columns: repeat(3, 1fr); }
}
</style>
