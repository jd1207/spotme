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
