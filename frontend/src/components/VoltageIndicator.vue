<script setup>
import { computed } from 'vue'

const props = defineProps({
  voltage: { type: Number, default: 0 },
  rpm: { type: Number, default: 0 },
})

const status = computed(() => {
  const v = props.voltage
  // Translated diagnostic messages for the charging system
  if (v < 12.0) return props.rpm > 1000 ? 'Alternator fault' : 'Battery'
  if (v > 14.8) return 'Regulator fault?'
  if (v >= 13.2) return 'Charging OK'
  return 'Low'
})

const colorVar = computed(() => {
  const v = props.voltage
  if (v < 12.0 || v > 14.8) return 'var(--c-danger)'
  if (v >= 13.2) return 'var(--c-success)'
  return 'var(--c-warn)'
})
</script>

<template>
  <div class="gauge">
    <div class="header">
      <!-- Translated from VOLTAJE to VOLTAGE -->
      <span class="label">VOLTAGE</span>
      <span class="status" :style="{ color: colorVar }">{{ status }}</span>
    </div>
    <div class="value" :style="{ color: colorVar }">
      {{ voltage.toFixed(1) }}<span class="unit">V</span>
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
</style>