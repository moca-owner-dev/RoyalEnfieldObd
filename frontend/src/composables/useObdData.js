import { ref, onMounted, onUnmounted } from 'vue'

/**
 * Composable que poll-ea /api/data y /api/session a un intervalo dado.
 * Devuelve refs reactivos: data, session, healthy.
 */
export function useObdData(intervalMs = 500) {
  const data = ref({
    connected: false,
    rpm: 0,
    speed: 0,
    tps: 0,
    map: 0,
    iat: 25,
    eot: 0,
    load: 0,
    voltage: 0,
    fuel_lh: 0,
    gear: null,
    last_update: null,
  })

  const session = ref({
    elapsed_min: 0,
    v_max: 0,
    rpm_max: 0,
    eot_max: 0,
    fuel_total_l: 0,
  })

  const healthy = ref(false)
  let timer = null

  async function poll() {
    try {
      const [dataRes, sessionRes] = await Promise.all([
        fetch('/api/data'),
        fetch('/api/session'),
      ])
      if (dataRes.ok) data.value = await dataRes.json()
      if (sessionRes.ok) session.value = await sessionRes.json()
      healthy.value = true
    } catch (err) {
      healthy.value = false
    }
  }

  async function resetSession() {
    try {
      await fetch('/api/session/reset', { method: 'POST' })
      await poll()
    } catch (err) {
      console.error('reset session failed', err)
    }
  }

  onMounted(() => {
    poll()
    timer = setInterval(poll, intervalMs)
  })

  onUnmounted(() => {
    if (timer) clearInterval(timer)
  })

  return { data, session, healthy, resetSession }
}
