import { onUnmounted, ref, shallowRef } from 'vue'

import type { JobEvent, JobSnapshot, JobStatus } from '@/api/types'

const RECONNECT_DELAY_MS = 2000
const MAX_LOG_ENTRIES = 200

const IDLE_STATUS: JobStatus = { state: 'idle', message: 'Sin búsquedas activas' }

export function useJobStream() {
  const status = ref<JobStatus>({ ...IDLE_STATUS })
  const events = ref<JobEvent[]>([])
  const connected = ref(false)

  const socket = shallowRef<WebSocket | null>(null)
  let reconnectTimer: ReturnType<typeof setTimeout> | undefined
  let closedByUs = false

  function connect() {
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const ws = new WebSocket(`${protocol}://${window.location.host}/api/jobs/stream`)
    socket.value = ws

    ws.onopen = () => {
      connected.value = true
    }

    ws.onmessage = (message) => {
      const payload = JSON.parse(message.data) as JobSnapshot | JobEvent
      if (payload.type === 'snapshot') {
        status.value = payload.status
        events.value = payload.events
        return
      }
      applyEvent(payload)
    }

    ws.onclose = () => {
      connected.value = false
      if (!closedByUs) {
        reconnectTimer = setTimeout(connect, RECONNECT_DELAY_MS)
      }
    }
  }

  function applyEvent(event: JobEvent) {
    if (event.type === 'state') {
      status.value = { ...status.value, state: event.state, message: event.message }
    } else if (event.type === 'attempt') {
      status.value = { ...status.value, attempts: event.attempts }
    }

    events.value = [...events.value, event].slice(-MAX_LOG_ENTRIES)
  }

  function disconnect() {
    closedByUs = true
    clearTimeout(reconnectTimer)
    socket.value?.close()
  }

  connect()
  onUnmounted(disconnect)

  return { status, events, connected }
}
