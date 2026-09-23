<script setup lang="ts">
import { computed, ref } from 'vue'

import type { JourneyType, Profile } from '@/api/types'

const props = defineProps<{
  profiles: Profile[]
  selectedProfileId: number | null
  busy: boolean
}>()

const emit = defineEmits<{
  (e: 'update:selectedProfileId', value: number | null): void
  (e: 'submit', value: { journey_type: JourneyType; date: string }): void
  (e: 'manage'): void
}>()

const journeyType = ref<JourneyType>('ida')
const date = ref('')

const canSubmit = computed(
  () => !props.busy && props.selectedProfileId !== null && date.value !== '',
)

function onSubmit() {
  if (!canSubmit.value) return
  emit('submit', {
    journey_type: journeyType.value,
    date: toRenfeDate(date.value),
  })
}

/** Renfe's date field expects dd/mm/yyyy; the native picker yields yyyy-mm-dd. */
function toRenfeDate(isoDate: string): string {
  const [year, month, day] = isoDate.split('-')
  return `${day}/${month}/${year}`
}
</script>

<template>
  <form class="card" @submit.prevent="onSubmit">
    <h2 class="card__title">Nueva búsqueda</h2>

    <div class="form-grid">
      <div class="field field--wide">
        <label class="field__label" for="profile">Perfil</label>
        <div class="profile-row">
          <select
            id="profile"
            class="select"
            :value="selectedProfileId ?? ''"
            :disabled="profiles.length === 0"
            @change="
              emit(
                'update:selectedProfileId',
                ($event.target as HTMLSelectElement).value
                  ? Number(($event.target as HTMLSelectElement).value)
                  : null,
              )
            "
          >
            <option v-if="profiles.length === 0" value="">Sin perfiles guardados</option>
            <option v-for="profile in profiles" :key="profile.id" :value="profile.id">
              {{ profile.username }} · {{ profile.abono }}
            </option>
          </select>
          <button type="button" class="btn btn--ghost" @click="emit('manage')">Gestionar</button>
        </div>
      </div>

      <div class="field">
        <label class="field__label" for="journey">Trayecto</label>
        <select id="journey" v-model="journeyType" class="select">
          <option value="ida">Ida</option>
          <option value="vuelta">Vuelta</option>
        </select>
      </div>

      <div class="field">
        <label class="field__label" for="date">Fecha</label>
        <input id="date" v-model="date" class="input" type="date" required />
      </div>
    </div>

    <button type="submit" class="btn btn--primary submit" :disabled="!canSubmit">
      {{ busy ? 'Búsqueda en curso…' : 'Ver trenes del día' }}
    </button>

    <p v-if="profiles.length === 0" class="hint">
      Crea un perfil con tus credenciales de Renfe para poder buscar.
    </p>
  </form>
</template>

<style scoped>
.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.field--wide {
  grid-column: 1 / -1;
}

.profile-row {
  display: flex;
  gap: 8px;
}

.profile-row .select {
  flex: 1;
}

.submit {
  width: 100%;
  margin-top: 20px;
}

.hint {
  margin: 12px 0 0;
  font-size: 13px;
  color: var(--text-muted);
  text-align: center;
}

@media (max-width: 520px) {
  .form-grid {
    grid-template-columns: 1fr;
  }
}
</style>
