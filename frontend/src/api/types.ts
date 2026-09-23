export type JourneyType = 'ida' | 'vuelta'

export type JobState =
  | 'idle'
  | 'starting'
  | 'logging_in'
  | 'opening_pass'
  | 'awaiting_human'
  | 'awaiting_code'
  | 'searching'
  | 'awaiting_train'
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

/** A row of Renfe's results table; `cells` holds whatever columns Renfe shows. */
export interface Train {
  departure: string
  cells: Record<string, string>
}

export interface JobSearch {
  username: string
  departure_time: string | null
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
  trains?: Train[]
}

export interface StartJobInput {
  user_id: number
  departure_time?: string
  journey_type: JourneyType
  date: string
}

/** Progress worth keeping in the log. */
export type JobEvent =
  | { type: 'state'; ts: string; state: JobState; message: string }
  | { type: 'log'; ts: string; message: string }
  | { type: 'attempt'; ts: string; attempts: number }

/** Everything the job stream can send; only `JobEvent`s end up in the log. */
export type StreamMessage =
  | JobEvent
  | { type: 'snapshot'; status: JobStatus; events: JobEvent[] }
  | { type: 'trains'; trains: Train[] }
  | { type: 'search'; search: JobSearch }
