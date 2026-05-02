<script setup>
import { computed } from 'vue'

const props = defineProps({
  speed: { type: Number, default: 0 },
  // Adjusted for J-series: 150 is a better scale for the 350cc than 200
  max: { type: Number, default: 150 },
})

const speedColor = computed(() => {
  // Keeping standard safety thresholds: warn at 80, danger at 100
  if (props.speed > 100) return 'var(--c-danger)'
  if (props.speed > 80) return 'var(--c-warn)'
  return 'var(--c-fg)'
})

const fillPct = computed(() => Math.min(100, (props.speed / props.max) * 100))
</script>

<template>
  <div class="gauge">
    <!-- Translated from VELOCIDAD to SPEED -->
    <div class="label">SPEED</div>
    <div class="value" :style="{ color: speedColor }">
      {{ Math.round(speed) }}
      <span class="unit">km/h</span>
    </div>
    <div class="bar-wrap">
      <div class="bar-fill" :style="{ width: fillPct + '%', background: speedColor }" />
    </div>
    <div class="scale">
      <span>0</span><span>{{ max / 2 }}</span><span>{{ max }}</span>
    </div>
  </div>
</template>

<style scoped>
.gauge {
  background: var(--c-panel);
  border-radius: 12px;
  padding: 1.5rem;
  border: 1px solid var(--c-border);
}
.label {
  font-size: 0.85rem;
  letter-spacing: 0.15em;
  color: var(--c-muted);
  margin-bottom: 0.5rem;
}
.value {
  font-size: 5.5rem;
  font-weight: 700;
  line-height: 1;
  font-variant-numeric: tabular-nums;
  transition: color 0.2s;
}
.unit {
  font-size: 1.5rem;
  font-weight: 400;
  color: var(--c-muted);
  margin-left: 0.3rem;
}
.bar-wrap {
  margin-top: 1rem;
  height: 12px;
  background: var(--c-bar-bg);
  border-radius: 6px;
  overflow: hidden;
}
.bar-fill {
  height: 100%;
  transition: width 0.3s, background 0.2s;
  border-radius: 6px;
}
.scale {
  display: flex;
  justify-content: space-between;
  margin-top: 0.4rem;
  color: var(--c-muted);
  font-size: 0.75rem;
}
</style>