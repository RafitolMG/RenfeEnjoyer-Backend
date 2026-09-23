import { onUnmounted, ref, shallowRef } from 'vue'

import type { JobEvent, JobStatus, StreamMessage } from '@/api/types'

const RECONNECT_DELAY_MS = 2000
const MAX_LOG_ENTRIES = 200

const IDLE_STATUS: JobStatus = { state: 'idle', message: 'Sin búsquedas activas' }

/**
 * The job stream is the only source of truth for job state. Action endpoints also
 * return a status, but applying it could overwrite a newer state that the socket had
 * already delivered, so callers should ignore it.
 */
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
      apply(JSON.parse(message.data) as StreamMessage)
    }

    ws.onclose = () => {
      connected.value = false
      if (!closedByUs) {
        reconnectTimer = setTimeout(connect, RECONNECT_DELAY_MS)
      }
    }
  }

  function apply(message: StreamMessage) {
    switch (message.type) {
      case 'snapshot':
        status.value = message.status
        events.value = message.events
        return
      case 'trains':
        status.value = { ...status.value, trains: message.trains }
        return
      case 'search':
        status.value = { ...status.value, search: message.search }
        return
      case 'state':
        status.value = { ...status.value, state: message.state, message: message.message }
        break
      case 'attempt':
        status.value = { ...status.value, attempts: message.attempts }
        break
    }
    events.value = [...events.value, message].slice(-MAX_LOG_ENTRIES)
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
