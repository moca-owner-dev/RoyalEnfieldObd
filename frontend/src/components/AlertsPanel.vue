<script setup>
import { computed } from 'vue'

const props = defineProps({
  data: { type: Object, required: true },
})

const alerts = computed(() => {
  const list = []
  const { eot, rpm, voltage } = props.data

  // Adjusted EOT for 350cc: 125°C is critical, 115°C is a warning
  if (eot >= 125) list.push({ level: 'crit', text: '🚨 CRITICAL EOT: Stop the bike' })
  else if (eot >= 115) list.push({ level: 'warn', text: '⚠ High EOT: Reduce pace' })

  // J-series Redline adjustment: Setting warning at 6500 RPM for the 350cc engine
  if (rpm > 6500) list.push({ level: 'crit', text: `⚠ RPM in redline (${Math.round(rpm)})` })

  if (voltage < 12.0 && rpm > 1000)
    list.push({ level: 'crit', text: '⚠ Low voltage with engine running — alternator?' })

  if (voltage > 14.8) list.push({ level: 'crit', text: '⚠ High voltage — regulator?' })

  if (eot < 60 && rpm > 4000)
    list.push({ level: 'warn', text: '⚠ Cold engine with high RPM — wait to warm up' })

  return list
})
</script>

<template>
  <div v-if="alerts.length" class="alerts">
    <div v-for="(a, i) in alerts" :key="i" class="alert" :class="a.level">
      {{ a.text }}
    </div>
  </div>
  <div v-else class="alerts ok">
    <div class="alert ok">✓ System OK</div>
  </div>
</template>

<style scoped>
/* Styles remain the same to maintain the Guatemala-designed aesthetic */
.alerts {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.alert {
  padding: 0.7rem 1rem;
  border-radius: 8px;
  font-weight: 600;
  font-size: 1rem;
  border: 1px solid var(--c-border);
}
.alert.crit {
  background: rgba(220, 50, 47, 0.15);
  border-color: var(--c-danger);
  color: var(--c-danger);
  animation: pulse 1s infinite;
}
.alert.warn {
  background: rgba(220, 165, 0, 0.12);
  border-color: var(--c-warn);
  color: var(--c-warn);
}
.alert.ok {
  background: rgba(0, 170, 90, 0.08);
  border-color: var(--c-success);
  color: var(--c-success);
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}
</style>