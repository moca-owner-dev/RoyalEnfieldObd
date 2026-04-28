<script setup>
import { computed } from 'vue'

const props = defineProps({
  gear: { type: Number, default: null },
  speed: { type: Number, default: 0 },
  rpm: { type: Number, default: 0 },
})

const display = computed(() => {
  if (props.gear) return String(props.gear)
  if (props.rpm > 800 && props.speed < 5) return 'N'
  if (props.rpm < 300) return '—'
  return '?'
})

const isReal = computed(() => props.gear !== null)
</script>

<template>
  <div class="gauge">
    <div class="label">MARCHA</div>
    <div class="gear" :class="{ active: isReal }">{{ display }}</div>
  </div>
</template>

<style scoped>
.gauge {
  background: var(--c-panel);
  border-radius: 12px;
  padding: 1.5rem;
  border: 1px solid var(--c-border);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}
.label {
  font-size: 0.85rem;
  letter-spacing: 0.15em;
  color: var(--c-muted);
  margin-bottom: 0.5rem;
}
.gear {
  font-size: 7rem;
  font-weight: 800;
  line-height: 1;
  color: var(--c-muted);
  font-variant-numeric: tabular-nums;
}
.gear.active {
  color: var(--c-success);
}
</style>
