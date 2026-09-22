<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { api } from '@/api/client'
import type { JourneyType, Profile } from '@/api/types'
import JobMonitor from '@/components/JobMonitor.vue'
import ProfileDialog from '@/components/ProfileDialog.vue'
import SearchForm from '@/components/SearchForm.vue'
import { useJobStream } from '@/composables/useJobStream'
import { occupiesBrowser } from '@/jobState'

const { status, events, connected } = useJobStream()

const profiles = ref<Profile[]>([])
const selectedProfileId = ref<number | null>(null)
const dialogOpen = ref(false)
const error = ref('')

const busy = computed(() => occupiesBrowser(status.value.state))

async function loadProfiles() {
  try {
    profiles.value = await api.listProfiles()
    const stillExists = profiles.value.some((p) => p.id === selectedProfileId.value)
    if (!stillExists) {
      selectedProfileId.value = profiles.value[0]?.id ?? null
    }
  } catch (cause) {
    error.value = (cause as Error).message
  }
}

async function startSearch(input: {
  departure_time: string
  journey_type: JourneyType
  date: string
}) {
  if (selectedProfileId.value === null) return
  error.value = ''
  try {
    status.value = await api.startJob({ user_id: selectedProfileId.value, ...input })
  } catch (cause) {
    error.value = (cause as Error).message
  }
}

async function run(action: () => Promise<typeof status.value>) {
  error.value = ''
  try {
    status.value = await action()
  } catch (cause) {
    error.value = (cause as Error).message
  }
}

onMounted(loadProfiles)
</script>

<template>
  <div class="shell">
    <header class="masthead">
      <div class="brand">
        <span class="brand__mark" aria-hidden="true" />
        <div>
          <h1 class="brand__name">Renfe Enjoyer</h1>
          <p class="brand__tagline">Caza plazas de abono automáticamente</p>
        </div>
      </div>
    </header>

    <p v-if="error" class="error-text banner">{{ error }}</p>

    <main class="layout">
      <SearchForm
        v-model:selected-profile-id="selectedProfileId"
        :profiles="profiles"
        :busy="busy"
        @submit="startSearch"
        @manage="dialogOpen = true"
      />
      <JobMonitor
        :status="status"
        :events="events"
        :connected="connected"
        @stop="run(api.stopJob)"
        @release="run(api.releaseJob)"
      />
    </main>

    <ProfileDialog
      v-if="dialogOpen"
      :profiles="profiles"
      @close="dialogOpen = false"
      @changed="loadProfiles"
    />
  </div>
</template>

<style scoped>
.shell {
  max-width: 1080px;
  margin: 0 auto;
  padding: 40px 24px 64px;
}

.masthead {
  margin-bottom: 28px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 14px;
}

.brand__mark {
  width: 38px;
  height: 38px;
  border-radius: 11px;
  background: linear-gradient(135deg, var(--accent), var(--accent-strong));
  box-shadow: 0 6px 18px color-mix(in srgb, var(--accent) 40%, transparent);
}

.brand__name {
  font-size: 22px;
}

.brand__tagline {
  margin: 2px 0 0;
  font-size: 13px;
  color: var(--text-muted);
}

.banner {
  margin: 0 0 18px;
  padding: 12px 14px;
  border-radius: var(--radius-sm);
  border: 1px solid color-mix(in srgb, var(--danger) 40%, transparent);
  background: color-mix(in srgb, var(--danger) 10%, transparent);
}

.layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 20px;
  align-items: start;
}

@media (max-width: 860px) {
  .layout {
    grid-template-columns: 1fr;
  }
}
</style>
