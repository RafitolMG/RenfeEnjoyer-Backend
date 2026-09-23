<script setup lang="ts">
import { computed, ref } from 'vue'

import type { Train } from '@/api/types'

const DEPARTURE_LABEL = 'Salida'

const props = defineProps<{ trains: Train[] }>()
const emit = defineEmits<{ (e: 'choose', departure: string): void }>()

const selected = ref<string | null>(null)

// Renfe's columns are not known in advance, so they are taken from the rows themselves.
const columns = computed(() => {
  const labels = new Set<string>([DEPARTURE_LABEL])
  for (const train of props.trains) {
    for (const label of Object.keys(train.cells)) labels.add(label)
  }
  return [...labels]
})

function confirm() {
  if (selected.value) emit('choose', selected.value)
}
</script>

<template>
  <form class="picker" @submit.prevent="confirm">
    <p class="picker__hint">
      Marca el tren que quieres. El bot recargará la página hasta que tenga plaza libre.
    </p>

    <div class="picker__scroll">
      <table class="picker__table">
        <thead>
          <tr>
            <th scope="col"><span class="sr-only">Elegir</span></th>
            <th v-for="column in columns" :key="column" scope="col">{{ column }}</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="train in trains"
            :key="train.departure"
            :class="{ 'is-selected': selected === train.departure }"
            @click="selected = train.departure"
          >
            <td class="picker__radio">
              <input
                v-model="selected"
                type="radio"
                name="train"
                :value="train.departure"
                :aria-label="`Tren de las ${train.departure}`"
              />
            </td>
            <td v-for="column in columns" :key="column">{{ train.cells[column] ?? '—' }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <button type="submit" class="btn btn--primary picker__confirm" :disabled="!selected">
      {{ selected ? `Buscar plaza en el de las ${selected}` : 'Elige un tren' }}
    </button>
  </form>
</template>

<style scoped>
.picker {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.picker__hint {
  margin: 0;
  font-size: 14px;
  color: var(--text-muted);
}

.picker__scroll {
  overflow-x: auto;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
}

.picker__table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
  font-variant-numeric: tabular-nums;
}

.picker__table th {
  padding: 10px 12px;
  text-align: left;
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-muted);
  background: var(--surface-raised);
  border-bottom: 1px solid var(--border);
  white-space: nowrap;
}

.picker__table td {
  padding: 11px 12px;
  border-bottom: 1px solid var(--border);
  white-space: nowrap;
}

.picker__table tbody tr {
  cursor: pointer;
  transition: background 0.12s ease;
}

.picker__table tbody tr:last-child td {
  border-bottom: none;
}

.picker__table tbody tr:hover {
  background: var(--surface-raised);
}

.picker__table tbody tr.is-selected {
  background: color-mix(in srgb, var(--accent) 14%, transparent);
}

.picker__radio {
  width: 1%;
}

.picker__radio input {
  accent-color: var(--accent);
  width: 16px;
  height: 16px;
  cursor: pointer;
}

.picker__confirm {
  align-self: stretch;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0 0 0 0);
  white-space: nowrap;
}
</style>
