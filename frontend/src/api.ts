const BASE = '/api'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, { headers: { 'Content-Type': 'application/json' }, ...options })
  if (!resp.ok) throw new Error(`API error: ${resp.status}`)
  return resp.json()
}

export const api = {
  chat: (message: string, workoutId?: number) => request<import('./types').ChatResponse>('/chat', { method: 'POST', body: JSON.stringify({ message, workout_id: workoutId ?? null }) }),
  startWorkout: (type?: string) => request<{ id: number; date: string; status: string; resumed: boolean }>('/workout/start', { method: 'POST', body: JSON.stringify({ type: type ?? 'strength' }) }),
  getRecentWorkouts: () => request<Array<{ id: number; date: string; type: string; status: string; duration: number | null; exercises: Array<{ name: string; sets: Array<{ weight: number; reps: number; rpe: number | null }> }>; recovery: number | null }>>('/workout/recent'),
  getPrs: () => request<{ prs: Array<{ exercise: string; weight: number; reps: number; e1rm: number; date: string }> }>('/progress/prs'),
  getChatHistory: (workoutId: number) => request<Array<{ role: string; content: string; created_at: string }>>(`/chat/history/${workoutId}`),
  intake: (data: Record<string, string>) => request<{ status: string; response: string | null }>('/intake', { method: 'POST', body: JSON.stringify(data) }),
  getNextWorkout: () => request<{ summary: string }>('/workout/next'),
  getTodayWorkout: () => request<import('./types').WorkoutData>('/workout/today'),
  getLastExercise: (name: string) => request<{ sets: Array<{ weight: number; reps: number; rpe: number | null; date: string }> }>(`/exercise/last/${encodeURIComponent(name)}`),
  logSet: (set: import('./types').SetLog) => request<{ id: number; logged: boolean }>('/workout/set', { method: 'POST', body: JSON.stringify(set) }),
  completeWorkout: (workoutId: number) => request<{ status: string; whoop_synced: boolean }>('/workout/complete', { method: 'POST', body: JSON.stringify({ workout_id: workoutId }) }),
  getLayout: (screen: string) => request<import('./types').Layout>(`/layout?screen=${screen}`),
  getProgram: () => request<{ has_program: boolean; weeks: Array<{ number: number; title: string; days: Array<{ day_of_week: string; type: string; planned: string; note: string; status: string }> }>; progression: Array<{ week: number; weight: number; label: string }>; stats: { total_workouts: number; completed_workouts: number; today: string } }>('/program'),
  getProgress: () => request<import('./types').ProgressData>('/progress'),
  getProfile: () => request<{ id: number; name: string } | null>('/profile'),
  whoopStatus: () => request<{ connected: boolean; oauth_available: boolean; write_enabled: boolean }>('/whoop/status'),
  whoopLogin: (email: string, password: string) => request<{ success: boolean; error?: string }>('/whoop/login', { method: 'POST', body: JSON.stringify({ email, password }) }),
  whoopAuthorize: () => request<{ url?: string; error?: string }>('/whoop/authorize'),
  whoopDisconnect: () => request<{ disconnected: boolean }>('/whoop/disconnect', { method: 'POST' }),
  syncWhoop: () => request<{ synced: number }>('/whoop/sync'),
  whoopLatest: () => request<{ data: { date: string; recovery_score: number | null; hrv: number | null; resting_hr: number | null; sleep_score: number | null; sleep_duration: number | null; strain: number | null } | null }>('/whoop/latest'),
  whoopTestWrite: () => request<{ success: boolean; activity_id?: number; error?: string; status_code?: number }>('/whoop/test-write', { method: 'POST' }),
  logMeal: (data: { description: string; calories?: number; protein?: number; carbs?: number; fat?: number; meal_type?: string }) => request<{ id: number; logged: boolean }>('/meals', { method: 'POST', body: JSON.stringify(data) }),
  getTodayMeals: () => request<{ date: string; meals: Array<{ id: number; description: string; calories: number | null; protein: number | null; carbs: number | null; fat: number | null; meal_type: string | null }>; totals: { calories: number; protein: number; carbs: number; fat: number } }>('/meals/today'),
  getWeekMeals: () => request<{ days: Array<{ date: string; calories: number; protein: number }> }>('/meals/week'),
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
