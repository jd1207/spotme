// detect /u/{user_id}/ prefix for multi-user routing
function getApiBase(): string {
  const match = window.location.pathname.match(/^\/u\/([a-zA-Z0-9_-]+)/)
  return match ? `/u/${match[1]}/api` : '/api'
}

const BASE = getApiBase()

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, { headers: { 'Content-Type': 'application/json' }, ...options })
  if (!resp.ok) throw new Error(`API error: ${resp.status}`)
  return resp.json()
}

export const api = {
  chat: (message: string, workoutId?: number, date?: string) => request<import('./types').ChatResponse>('/chat', { method: 'POST', body: JSON.stringify({ message, workout_id: workoutId ?? null, date: date ?? null }) }),
  startWorkout: (type?: string) => request<{ id: number; date: string; status: string; resumed: boolean }>('/workout/start', { method: 'POST', body: JSON.stringify({ type: type ?? 'strength' }) }),
  getRecentWorkouts: () => request<Array<{ id: number; date: string; type: string; status: string; duration: number | null; exercises: Array<{ name: string; sets: Array<{ weight: number; reps: number; rpe: number | null }> }>; recovery: number | null }>>('/workout/recent'),
  getPrs: () => request<{ prs: Array<{ exercise: string; weight: number; reps: number; e1rm: number; date: string }> }>('/progress/prs'),
  getChatHistory: (workoutId: number) => request<Array<{ role: string; content: string; created_at: string }>>(`/chat/history/${workoutId}`),
  getChatDays: () => request<{ days: Array<{ date: string; message_count: number; workout_type: string | null; recovery_score: number | null; recovery_zone: string | null; calories_total: number }> }>('/chat/days'),
  getChatDay: (date: string) => request<{ messages: Array<{ role: string; content: string; created_at: string }> }>(`/chat/day/${date}`),
  intake: (data: Record<string, string>) => request<{ status: string; response: string | null }>('/intake', { method: 'POST', body: JSON.stringify(data) }),
  getNextWorkout: () => request<{ summary: string }>('/workout/next'),
  getTodayWorkout: () => request<import('./types').WorkoutData>('/workout/today'),
  getLastExercise: (name: string) => request<{ sets: Array<{ weight: number; reps: number; rpe: number | null; date: string }> }>(`/exercise/last/${encodeURIComponent(name)}`),
  logSet: (set: import('./types').SetLog) => request<{ id: number; logged: boolean }>('/workout/set', { method: 'POST', body: JSON.stringify(set) }),
  completeWorkout: (workoutId: number) => request<{ status: string; whoop_synced: boolean }>('/workout/complete', { method: 'POST', body: JSON.stringify({ workout_id: workoutId }) }),
  completeSet: (data: { set_id: number; actual_weight: number; actual_reps: number; actual_rpe?: number; feel?: string }) => request<import('./types').CompleteSetResponse>('/workout/complete-set', { method: 'POST', body: JSON.stringify(data) }),
  getLayout: (screen: string) => request<import('./types').Layout>(`/layout?screen=${screen}`),
  getProgram: () => request<{ has_program: boolean; weeks: Array<{ number: number; title: string; days: Array<{ day_of_week: string; type: string; planned: string; note: string; status: string }> }>; progression: Array<{ week: number; weight: number; label: string }>; stats: { total_workouts: number; completed_workouts: number; today: string } }>('/program'),
  getProgramWeek: (weekNum: number) => request<{ week: number; days: Array<{ day_of_week: string; type: string; planned: string; note: string; status: string; source: string; exercises: Array<{ name: string; sets: Array<{ weight: number; reps: number; rpe: number | null; set_type: string; status: string; target_weight: number | null; target_reps: number | null }> }>; summary: { total_sets: number; top_set: string; avg_rpe: number | null } | null }> }>(`/program/week/${weekNum}`),
  getProgress: () => request<import('./types').ProgressData>('/progress'),
  getProfile: () => request<{ id: number; name: string; calorie_target: number | null; protein_target: number | null } | null>('/profile'),
  whoopStatus: () => request<{ connected: boolean }>('/whoop/status'),
  whoopLogin: (email: string, password: string) => request<{ connected?: boolean; success?: boolean; error?: string }>('/whoop/login', { method: 'POST', body: JSON.stringify({ email, password }) }),
  whoopDisconnect: () => request<{ disconnected: boolean }>('/whoop/disconnect', { method: 'POST' }),
  syncWhoop: () => request<{ synced: number }>('/whoop/sync'),
  whoopLatest: () => request<{ data: { date: string; recovery_score: number | null; hrv: number | null; resting_hr: number | null; sleep_score: number | null; sleep_duration: number | null; strain: number | null } | null }>('/whoop/latest'),
  logMeal: (data: { description: string; calories?: number; protein?: number; carbs?: number; fat?: number; meal_type?: string }) => request<{ id: number; logged: boolean }>('/meals', { method: 'POST', body: JSON.stringify(data) }),
  getTodayMeals: () => request<{ date: string; meals: Array<{ id: number; description: string; calories: number | null; protein: number | null; carbs: number | null; fat: number | null; meal_type: string | null; items: string[] | null; created_at: string | null }>; totals: { calories: number; protein: number; carbs: number; fat: number } }>('/meals/today'),
  getWeekMeals: () => request<{ days: Array<{ date: string; calories: number; protein: number }> }>('/meals/week'),
  getMealsDay: (date: string) => request<{ date: string; meals: Array<{ id: number; description: string; calories: number | null; protein: number | null; carbs: number | null; fat: number | null; meal_type: string | null; items: string[] | null; created_at: string | null }>; totals: { calories: number; protein: number; carbs: number; fat: number } }>(`/meals/day/${date}`),
  deleteMeal: (id: number) => request<{ deleted: boolean }>(`/meals/${id}`, { method: 'DELETE' }),
  uploadVideo: async (file: File, exercise: string, weight: number, setNumber: number) => {
    const form = new FormData()
    form.append('file', file)
    form.append('exercise', exercise)
    form.append('weight', weight.toString())
    form.append('set_number', setNumber.toString())
    const resp = await fetch(`${BASE}/video`, { method: 'POST', body: form })
    return resp.json()
  },
}
