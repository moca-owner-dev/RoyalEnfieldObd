<script setup>
import { computed } from 'vue'

const props = defineProps({
  rpm: { type: Number, default: 0 },
  // Adjusted for J-series: Redline is lower than the 650's 7400 RPM
  redline: { type: Number, default: 7000 },
  yellow: { type: Number, default: 6000 },
  green: { type: Number, default: 4500 },
})

const rpmColor = computed(() => {
  if (props.rpm >= props.yellow) return 'var(--c-danger)'
  if (props.rpm >= props.green) return 'var(--c-warn)'
  return 'var(--c-fg)'
})

const fillPct = computed(() => Math.min(100, (props.rpm / props.redline) * 100))

// Zone markers on the bar (English comments)
const greenPct = computed(() => (props.green / props.redline) * 100)
const yellowPct = computed(() => (props.yellow / props.redline) * 100)
</script>

<template>
  <div class="gauge">
    <div class="label">RPM</div>
    <div class="value" :style="{ color: rpmColor }">
      {{ Math.round(rpm) }}
    </div>
    <div class="bar-wrap">
      <!-- Zone markers -->
      <div class="zone zone-green" :style="{ width: greenPct + '%' }" />
      <div class="zone zone-yellow"
           :style="{ left: greenPct + '%', width: (yellowPct - greenPct) + '%' }" />
      <div class="zone zone-red"
           :style="{ left: yellowPct + '%', width: (100 - yellowPct) + '%' }" />
      <div class="bar-fill" :style="{ width: fillPct + '%', background: rpmColor }" />
    </div>
    <div class="scale">
      <span>0</span>
      <span>{{ green }}</span>
      <span>{{ yellow }}</span>
      <span>{{ redline }}</span>
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
.bar-wrap {
  position: relative;
  margin-top: 1rem;
  height: 16px;
  background: var(--c-bar-bg);
  border-radius: 8px;
  overflow: hidden;
}
.zone {
  position: absolute;
  top: 0;
  bottom: 0;
  opacity: 0.2;
}
.zone-green { left: 0; background: var(--c-success); }
.zone-yellow { background: var(--c-warn); }
.zone-red { background: var(--c-danger); }
.bar-fill {
  position: absolute;
  top: 0; left: 0; bottom: 0;
  transition: width 0.2s, background 0.2s;
  border-radius: 8px;
}
.scale {
  display: flex;
  justify-content: space-between;
  margin-top: 0.4rem;
  color: var(--c-muted);
  font-size: 0.75rem;
}
</style>