const BASE = '/api'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, { headers: { 'Content-Type': 'application/json' }, ...options })
  if (!resp.ok) throw new Error(`API error: ${resp.status}`)
  return resp.json()
}

export const api = {
  chat: (message: string, workoutId?: number) => request<import('./types').ChatResponse>('/chat', { method: 'POST', body: JSON.stringify({ message, workout_id: workoutId ?? null }) }),
  startWorkout: (type?: string) => request<{ id: number; date: string; status: string; resumed: boolean }>('/workout/start', { method: 'POST', body: JSON.stringify({ type: type ?? 'strength' }) }),
  getRecentWorkouts: () => request<Array<{ id: number; date: string; type: string; status: string; duration: number | null }>>('/workout/recent'),
  getChatHistory: (workoutId: number) => request<Array<{ role: string; content: string; created_at: string }>>(`/chat/history/${workoutId}`),
  intake: (data: Record<string, string>) => request<{ status: string; response: string | null }>('/intake', { method: 'POST', body: JSON.stringify(data) }),
  getNextWorkout: () => request<{ summary: string }>('/workout/next'),
  getTodayWorkout: () => request<import('./types').WorkoutData>('/workout/today'),
  logSet: (set: import('./types').SetLog) => request<{ id: number; logged: boolean }>('/workout/set', { method: 'POST', body: JSON.stringify(set) }),
  completeWorkout: (workoutId: number) => request<{ status: string; whoop_synced: boolean }>('/workout/complete', { method: 'POST', body: JSON.stringify({ workout_id: workoutId }) }),
  getLayout: (screen: string) => request<import('./types').Layout>(`/layout?screen=${screen}`),
  getProgress: () => request<{ bench_1rm_trend: object[]; whoop_trends: object }>('/progress'),
  getProfile: () => request<{ id: number; name: string } | null>('/profile'),
  whoopStatus: () => request<{ connected: boolean; oauth_available: boolean }>('/whoop/status'),
  whoopAuthorize: () => request<{ url?: string; error?: string }>('/whoop/authorize'),
  syncWhoop: () => request<{ synced: number }>('/whoop/sync'),
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
