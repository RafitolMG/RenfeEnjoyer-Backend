<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'

import type { JobEvent, JobStatus } from '@/api/types'
import StatusBadge from '@/components/StatusBadge.vue'
import { occupiesBrowser } from '@/jobState'

const props = defineProps<{
  status: JobStatus
  events: JobEvent[]
  connected: boolean
}>()

const emit = defineEmits<{ (e: 'stop'): void; (e: 'release'): void }>()

const logElement = ref<HTMLElement | null>(null)

const isReserved = computed(() => props.status.state === 'reserved')
const canStop = computed(() => occupiesBrowser(props.status.state))
const attempts = computed(() => props.status.attempts ?? 0)

const logLines = computed(() =>
  props.events.map((event, index) => ({
    key: `${event.ts}-${index}`,
    time: formatTime(event.ts),
    text: describe(event),
    tone: event.type === 'state' ? 'state' : 'log',
  })),
)

watch(
  () => props.events.length,
  async () => {
    await nextTick()
    logElement.value?.scrollTo({ top: logElement.value.scrollHeight })
  },
)

function describe(event: JobEvent): string {
  if (event.type === 'state') return event.message
  if (event.type === 'log') return event.message
  return `Intento ${event.attempts}`
}

function formatTime(timestamp: string): string {
  return new Date(timestamp).toLocaleTimeString('es-ES', { hour12: false })
}
</script>

<template>
  <section class="card monitor">
    <header class="monitor__header">
      <h2 class="card__title monitor__heading">Estado</h2>
      <span class="link" :class="{ 'link--down': !connected }" :title="connected ? 'Conectado' : 'Reconectando…'" />
    </header>

    <StatusBadge :state="status.state" />
    <p class="monitor__message">{{ status.message }}</p>

    <dl v-if="status.search" class="summary">
      <div><dt>Perfil</dt><dd>{{ status.search.username }}</dd></div>
      <div><dt>Salida</dt><dd>{{ status.search.departure_time }}</dd></div>
      <div><dt>Trayecto</dt><dd>{{ status.search.journey_type }}</dd></div>
      <div><dt>Fecha</dt><dd>{{ status.search.date }}</dd></div>
    </dl>

    <p v-if="attempts > 0" class="attempts">
      <span class="attempts__value">{{ attempts }}</span>
      <span class="attempts__label">recargas de la página</span>
    </p>

    <div v-if="isReserved" class="callout">
      <strong>Plaza reservada.</strong>
      Completa la compra en la ventana del navegador que ha abierto el bot. Cuando termines,
      cierra la sesión desde aquí.
    </div>

    <ul v-if="logLines.length" ref="logElement" class="log">
      <li v-for="line in logLines" :key="line.key" class="log__line" :class="`log__line--${line.tone}`">
        <time>{{ line.time }}</time>
        <span>{{ line.text }}</span>
      </li>
    </ul>
    <p v-else class="empty">El progreso de la búsqueda aparecerá aquí.</p>

    <footer v-if="canStop" class="monitor__actions">
      <button v-if="isReserved" class="btn btn--primary" @click="emit('release')">
        He terminado, cerrar navegador
      </button>
      <button class="btn btn--danger" @click="emit('stop')">Detener búsqueda</button>
    </footer>
  </section>
</template>

<style scoped>
.monitor {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 14px;
}

.monitor__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.monitor__heading {
  margin-bottom: 0;
}

.link {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--success);
}

.link--down {
  background: var(--danger);
}

.monitor__message {
  margin: 0;
  color: var(--text-muted);
}

.summary {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px 20px;
  width: 100%;
  margin: 0;
  padding: 14px;
  background: var(--surface-raised);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
}

.summary dt {
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-muted);
}

.summary dd {
  margin: 2px 0 0;
  font-weight: 600;
}

.attempts {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin: 0;
}

.attempts__value {
  font-size: 30px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: var(--accent-strong);
}

.attempts__label {
  font-size: 13px;
  color: var(--text-muted);
}

.callout {
  width: 100%;
  padding: 14px;
  border-radius: var(--radius-sm);
  border: 1px solid color-mix(in srgb, var(--success) 45%, transparent);
  background: color-mix(in srgb, var(--success) 10%, transparent);
  font-size: 14px;
}

.log {
  width: 100%;
  max-height: 260px;
  overflow-y: auto;
  margin: 0;
  padding: 12px;
  list-style: none;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font-family: var(--font-mono);
  font-size: 12.5px;
}

.log__line {
  display: flex;
  gap: 12px;
  padding: 2px 0;
  color: var(--text-muted);
}

.log__line--state {
  color: var(--text);
}

.log__line time {
  flex-shrink: 0;
  opacity: 0.6;
}

.empty {
  width: 100%;
  margin: 0;
  padding: 24px;
  text-align: center;
  color: var(--text-muted);
  font-size: 13px;
  border: 1px dashed var(--border-strong);
  border-radius: var(--radius-sm);
}

.monitor__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  width: 100%;
}
</style>
