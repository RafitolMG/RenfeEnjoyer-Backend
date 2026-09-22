<script setup lang="ts">
import { onMounted, onUnmounted, reactive, ref } from 'vue'

import { api } from '@/api/client'
import type { Profile } from '@/api/types'

const props = defineProps<{ profiles: Profile[] }>()
const emit = defineEmits<{ (e: 'close'): void; (e: 'changed'): void }>()

const mode = ref<'list' | 'form'>(props.profiles.length === 0 ? 'form' : 'list')
const editing = ref<Profile | null>(null)
const error = ref('')
const saving = ref(false)

const form = reactive({ username: '', email: '', password: '', abono: '' })

function openCreate() {
  editing.value = null
  Object.assign(form, { username: '', email: '', password: '', abono: '' })
  error.value = ''
  mode.value = 'form'
}

function openEdit(profile: Profile) {
  editing.value = profile
  // The API never returns the stored password; blank means "keep it".
  Object.assign(form, {
    username: profile.username,
    email: profile.email,
    password: '',
    abono: profile.abono,
  })
  error.value = ''
  mode.value = 'form'
}

async function save() {
  saving.value = true
  error.value = ''
  try {
    if (editing.value) {
      await api.updateProfile(editing.value.id, { ...form })
    } else {
      await api.createProfile({ ...form })
    }
    emit('changed')
    mode.value = 'list'
  } catch (cause) {
    error.value = (cause as Error).message
  } finally {
    saving.value = false
  }
}

async function remove(profile: Profile) {
  if (!window.confirm(`¿Eliminar el perfil "${profile.username}"?`)) return
  try {
    await api.deleteProfile(profile.id)
    emit('changed')
  } catch (cause) {
    error.value = (cause as Error).message
  }
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') emit('close')
}

onMounted(() => window.addEventListener('keydown', onKeydown))
onUnmounted(() => window.removeEventListener('keydown', onKeydown))
</script>

<template>
  <div class="overlay" @click.self="emit('close')">
    <div class="dialog" role="dialog" aria-modal="true" aria-label="Perfiles">
      <header class="dialog__header">
        <h2>{{ mode === 'list' ? 'Perfiles' : editing ? 'Editar perfil' : 'Nuevo perfil' }}</h2>
        <button class="close" aria-label="Cerrar" @click="emit('close')">×</button>
      </header>

      <p v-if="error" class="error-text">{{ error }}</p>

      <template v-if="mode === 'list'">
        <ul class="profiles">
          <li v-for="profile in profiles" :key="profile.id" class="profiles__item">
            <div>
              <p class="profiles__name">{{ profile.username }}</p>
              <p class="profiles__meta">{{ profile.email }} · abono {{ profile.abono }}</p>
            </div>
            <div class="profiles__actions">
              <button class="btn btn--ghost" @click="openEdit(profile)">Editar</button>
              <button class="btn btn--danger" @click="remove(profile)">Eliminar</button>
            </div>
          </li>
        </ul>
        <button class="btn btn--primary full" @click="openCreate">Nuevo perfil</button>
      </template>

      <form v-else class="form" @submit.prevent="save">
        <div class="field">
          <label class="field__label" for="username">Nombre del perfil</label>
          <input id="username" v-model="form.username" class="input" required />
        </div>
        <div class="field">
          <label class="field__label" for="email">Correo de Renfe</label>
          <input id="email" v-model="form.email" class="input" type="email" required />
        </div>
        <div class="field">
          <label class="field__label" for="password">Contraseña</label>
          <input
            id="password"
            v-model="form.password"
            class="input"
            type="password"
            :required="!editing"
            :placeholder="editing ? 'Dejar vacío para no cambiarla' : ''"
          />
        </div>
        <div class="field">
          <label class="field__label" for="abono">Abono</label>
          <input id="abono" v-model="form.abono" class="input" required />
        </div>

        <div class="form__actions">
          <button
            v-if="profiles.length"
            type="button"
            class="btn btn--ghost"
            @click="mode = 'list'"
          >
            Volver
          </button>
          <button type="submit" class="btn btn--primary" :disabled="saving">
            {{ saving ? 'Guardando…' : 'Guardar' }}
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  display: grid;
  place-items: center;
  padding: 20px;
  background: rgb(0 0 0 / 55%);
  backdrop-filter: blur(3px);
  z-index: 10;
}

.dialog {
  width: min(520px, 100%);
  max-height: 85vh;
  overflow-y: auto;
  padding: 24px;
  background: var(--surface);
  border: 1px solid var(--border-strong);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
}

.dialog__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 18px;
}

.dialog__header h2 {
  font-size: 18px;
}

.close {
  background: none;
  border: none;
  font-size: 26px;
  line-height: 1;
  color: var(--text-muted);
  cursor: pointer;
}

.close:hover {
  color: var(--text);
}

.profiles {
  list-style: none;
  margin: 0 0 16px;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.profiles__item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px;
  background: var(--surface-raised);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
}

.profiles__name {
  margin: 0;
  font-weight: 600;
}

.profiles__meta {
  margin: 2px 0 0;
  font-size: 13px;
  color: var(--text-muted);
}

.profiles__actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.form__actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 6px;
}

.full {
  width: 100%;
}

@media (max-width: 480px) {
  .profiles__item {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
