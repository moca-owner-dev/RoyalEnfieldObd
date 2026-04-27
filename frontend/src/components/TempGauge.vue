<script setup>
import { computed } from 'vue'

const props = defineProps({
  label: { type: String, required: true },
  value: { type: Number, default: 0 },
  unit: { type: String, default: '°C' },
  cold: { type: Number, default: 60 },
  normal: { type: Number, default: 105 },
  warning: { type: Number, default: 115 },
  danger: { type: Number, default: 125 },
  max: { type: Number, default: 140 },
})

const status = computed(() => {
  if (props.value >= props.danger) return 'DETENER MOTO'
  if (props.value >= props.warning) return 'ALTO'
  if (props.value >= props.cold) return 'Normal'
  return 'Frío'
})

const colorVar = computed(() => {
  if (props.value >= props.warning) return 'var(--c-danger)'
  if (props.value >= props.normal) return 'var(--c-warn)'
  if (props.value < props.cold) return 'var(--c-info)'
  return 'var(--c-success)'
})

const fillPct = computed(() => Math.min(100, Math.max(0, (props.value / props.max) * 100)))
</script>

<template>
  <div class="gauge">
    <div class="header">
      <span class="label">{{ label }}</span>
      <span class="status" :style="{ color: colorVar }">{{ status }}</span>
    </div>
    <div class="value" :style="{ color: colorVar }">
      {{ Math.round(value) }}<span class="unit">{{ unit }}</span>
    </div>
    <div class="bar-wrap">
      <div class="bar-fill" :style="{ width: fillPct + '%', background: colorVar }" />
    </div>
  </div>
</template>

<style scoped>
.gauge {
  background: var(--c-panel);
  border-radius: 10px;
  padding: 1rem 1.2rem;
  border: 1px solid var(--c-border);
}
.header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 0.4rem;
}
.label {
  font-size: 0.75rem;
  letter-spacing: 0.12em;
  color: var(--c-muted);
}
.status {
  font-size: 0.8rem;
  font-weight: 600;
}
.value {
  font-size: 2.5rem;
  font-weight: 700;
  line-height: 1;
  font-variant-numeric: tabular-nums;
  transition: color 0.2s;
}
.unit {
  font-size: 1rem;
  color: var(--c-muted);
  margin-left: 0.2rem;
}
.bar-wrap {
  margin-top: 0.6rem;
  height: 6px;
  background: var(--c-bar-bg);
  border-radius: 3px;
  overflow: hidden;
}
.bar-fill {
  height: 100%;
  transition: width 0.3s, background 0.2s;
}
</style>
