<script setup>
import { computed } from 'vue'

const props = defineProps({
  data: { type: Object, required: true },
})

const alerts = computed(() => {
  const list = []
  const { eot, rpm, voltage } = props.data

  if (eot >= 125) list.push({ level: 'crit', text: '🚨 EOT CRÍTICA: detené la moto' })
  else if (eot >= 115) list.push({ level: 'warn', text: '⚠ EOT alta: bajá ritmo' })

  if (rpm > 7200) list.push({ level: 'crit', text: `⚠ RPM en redline (${Math.round(rpm)})` })

  if (voltage < 12.0 && rpm > 1000)
    list.push({ level: 'crit', text: '⚠ Voltaje bajo con motor andando — alternador?' })

  if (voltage > 14.8) list.push({ level: 'crit', text: '⚠ Voltaje alto — regulador?' })

  if (eot < 60 && rpm > 4000)
    list.push({ level: 'warn', text: '⚠ Motor frío con RPM alto — esperá que caliente' })

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
    <div class="alert ok">✓ Todo OK</div>
  </div>
</template>

<style scoped>
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
