import type { JobState } from '@/api/types'

export const JOB_STATE_LABELS: Record<JobState, string> = {
  idle: 'En reposo',
  starting: 'Arrancando',
  logging_in: 'Iniciando sesión',
  opening_pass: 'Abriendo abono',
  awaiting_human: 'Captcha pendiente',
  awaiting_code: 'Código requerido',
  searching: 'Configurando',
  awaiting_train: 'Elige tren',
  polling: 'Buscando plazas',
  reserved: 'Plaza reservada',
  finished: 'Finalizado',
  failed: 'Error',
  cancelled: 'Detenido',
}

export const JOB_STATE_TONES: Record<JobState, string> = {
  idle: 'muted',
  starting: 'info',
  logging_in: 'info',
  opening_pass: 'info',
  awaiting_human: 'warning',
  awaiting_code: 'warning',
  searching: 'info',
  awaiting_train: 'info',
  polling: 'warning',
  reserved: 'success',
  finished: 'muted',
  failed: 'danger',
  cancelled: 'muted',
}

/** States where the bot is parked until the user does something. */
const WAITING_ON_USER: readonly JobState[] = [
  'awaiting_human',
  'awaiting_code',
  'awaiting_train',
  'reserved',
]

/** States where a browser session is open, so no new search may start. */
const OCCUPIED: readonly JobState[] = [
  'starting',
  'logging_in',
  'opening_pass',
  'searching',
  'polling',
  ...WAITING_ON_USER,
]

export function occupiesBrowser(state: JobState): boolean {
  return OCCUPIED.includes(state)
}

/** States where the bot is still working, as opposed to waiting on the user. */
export function isWorking(state: JobState): boolean {
  return occupiesBrowser(state) && !WAITING_ON_USER.includes(state)
}
