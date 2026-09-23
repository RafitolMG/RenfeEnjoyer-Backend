export type JourneyType = 'ida' | 'vuelta'

export type JobState =
  | 'idle'
  | 'starting'
  | 'logging_in'
  | 'opening_pass'
  | 'awaiting_code'
  | 'searching'
  | 'polling'
  | 'reserved'
  | 'finished'
  | 'failed'
  | 'cancelled'

export interface Profile {
  id: number
  username: string
  email: string
  abono: string
}

export interface ProfileInput {
  username: string
  email: string
  password: string
  abono: string
}

export interface JobSearch {
  username: string
  departure_time: string
  journey_type: JourneyType
  date: string
  abono: string
}

export interface JobStatus {
  state: JobState
  message: string
  attempts?: number
  started_at?: string
  search?: JobSearch
}

export interface StartJobInput {
  user_id: number
  departure_time: string
  journey_type: JourneyType
  date: string
}

export type JobEvent =
  | { type: 'state'; ts: string; state: JobState; message: string }
  | { type: 'log'; ts: string; message: string }
  | { type: 'attempt'; ts: string; attempts: number }

export interface JobSnapshot {
  type: 'snapshot'
  status: JobStatus
  events: JobEvent[]
}
