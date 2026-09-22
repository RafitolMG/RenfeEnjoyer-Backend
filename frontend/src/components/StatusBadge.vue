<script setup lang="ts">
import { computed } from 'vue'

import type { JobState } from '@/api/types'
import { JOB_STATE_LABELS, JOB_STATE_TONES, isWorking } from '@/jobState'

const props = defineProps<{ state: JobState }>()

const label = computed(() => JOB_STATE_LABELS[props.state])
const tone = computed(() => JOB_STATE_TONES[props.state])
const pulsing = computed(() => isWorking(props.state))
</script>

<template>
  <span class="badge" :class="`badge--${tone}`">
    <span class="badge__dot" :class="{ 'badge__dot--pulse': pulsing }" />
    {{ label }}
  </span>
</template>

<style scoped>
.badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 5px 12px 5px 10px;
  border-radius: 999px;
  border: 1px solid currentcolor;
  font-size: 13px;
  font-weight: 600;
}

.badge--muted {
  color: var(--text-muted);
}
.badge--info {
  color: var(--info);
}
.badge--warning {
  color: var(--warning);
}
.badge--success {
  color: var(--success);
}
.badge--danger {
  color: var(--danger);
}

.badge__dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: currentcolor;
}

.badge__dot--pulse {
  animation: pulse 1.6s ease-in-out infinite;
}

@keyframes pulse {
  0%,
  100% {
    opacity: 1;
    box-shadow: 0 0 0 0 currentcolor;
  }
  50% {
    opacity: 0.55;
    box-shadow: 0 0 0 4px transparent;
  }
}

@media (prefers-reduced-motion: reduce) {
  .badge__dot--pulse {
    animation: none;
  }
}
</style>
