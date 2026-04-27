<script setup>
const props = defineProps({
  session: { type: Object, required: true },
  data: { type: Object, required: true },
})

const emit = defineEmits(['reset'])
</script>

<template>
  <div class="panel">
    <div class="head">
      <span class="label">SESIÓN</span>
      <button class="reset-btn" @click="emit('reset')">Reset</button>
    </div>
    <div class="grid">
      <div>
        <div class="stat-label">Duración</div>
        <div class="stat-val">{{ session.elapsed_min.toFixed(1) }} <span>min</span></div>
      </div>
      <div>
        <div class="stat-label">Vmax</div>
        <div class="stat-val">{{ Math.round(session.v_max) }} <span>km/h</span></div>
      </div>
      <div>
        <div class="stat-label">RPMmax</div>
        <div class="stat-val">{{ Math.round(session.rpm_max) }}</div>
      </div>
      <div>
        <div class="stat-label">EOTmax</div>
        <div class="stat-val">{{ session.eot_max.toFixed(1) }} <span>°C</span></div>
      </div>
      <div>
        <div class="stat-label">Combustible</div>
        <div class="stat-val">{{ session.fuel_total_l.toFixed(2) }} <span>L</span></div>
      </div>
      <div>
        <div class="stat-label">Consumo ahora</div>
        <div class="stat-val">{{ data.fuel_lh.toFixed(2) }} <span>L/h</span></div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.panel {
  background: var(--c-panel);
  border-radius: 10px;
  padding: 1rem 1.2rem;
  border: 1px solid var(--c-border);
}
.head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.6rem;
}
.label {
  font-size: 0.75rem;
  letter-spacing: 0.12em;
  color: var(--c-muted);
}
.reset-btn {
  background: transparent;
  color: var(--c-muted);
  border: 1px solid var(--c-border);
  padding: 0.3rem 0.6rem;
  border-radius: 6px;
  font-size: 0.7rem;
  cursor: pointer;
  letter-spacing: 0.1em;
}
.reset-btn:hover {
  color: var(--c-fg);
  border-color: var(--c-fg);
}
.grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.8rem 1rem;
}
.stat-label {
  font-size: 0.7rem;
  color: var(--c-muted);
  text-transform: uppercase;
  letter-spacing: 0.08em;
}
.stat-val {
  font-size: 1.2rem;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}
.stat-val span {
  font-size: 0.75rem;
  color: var(--c-muted);
  font-weight: 400;
}
</style>
