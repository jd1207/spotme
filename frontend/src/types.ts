export type ComponentType =
  | 'header' | 'stat_card' | 'exercise_card' | 'set_logger'
  | 'rest_timer' | 'text_block' | 'video_prompt' | 'chart'
  | 'action_button' | 'chat_bubble'

export interface LayoutComponent {
  type: ComponentType
  [key: string]: unknown
}

export interface Layout {
  screen: string
  layout: LayoutComponent[]
}

export interface ChatResponse {
  response: string
  layout: Layout | null
  set_suggestion?: SetSuggestion | null
}

export interface SetLog {
  exercise_name: string
  weight: number
  reps: number
  rpe?: number
  notes?: string
}

export interface ExerciseData {
  id: number
  name: string
  order: number
  sets: Array<{ id: number; weight: number; reps: number; rpe: number | null; completed: boolean }>
}

export interface WorkoutData {
  id: number
  date: string
  status: string
  exercises: ExerciseData[]
  whoop_recovery: number | null
}

export interface SetSuggestion {
  exercise: string
  weight: number
  reps: number
  basis?: string
  lastSet?: { weight: number; reps: number; rpe: number | null }
}

export interface Message {
  role: 'user' | 'assistant'
  content: string
  setCard?: SetSuggestion
}

export interface WhoopStats {
  recovery_score: number | null
  hrv: number | null
  resting_hr: number | null
  sleep_score: number | null
  sleep_duration: number | null
  strain: number | null
}

export interface SessionData {
  day: string
  type: string
  status: 'completed' | 'today' | 'upcoming'
  exercises?: string
  recovery?: number
  strain?: number
  duration?: number
}

export interface WeekData {
  number: number
  label: string
  sessions: SessionData[]
  completed: number
  total: number
}
