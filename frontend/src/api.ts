const BASE = '/api'

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, { headers: { 'Content-Type': 'application/json' }, ...options })
  if (!resp.ok) throw new Error(`API error: ${resp.status}`)
  return resp.json()
}

export const api = {
  chat: (message: string) => request<import('./types').ChatResponse>('/chat', { method: 'POST', body: JSON.stringify({ message }) }),
  getTodayWorkout: () => request<import('./types').WorkoutData>('/workout/today'),
  logSet: (set: import('./types').SetLog) => request<{ id: number; logged: boolean }>('/workout/set', { method: 'POST', body: JSON.stringify(set) }),
  completeWorkout: (workoutId: number) => request<{ status: string; whoop_synced: boolean }>('/workout/complete', { method: 'POST', body: JSON.stringify({ workout_id: workoutId }) }),
  getLayout: (screen: string) => request<import('./types').Layout>(`/layout?screen=${screen}`),
  getProgress: () => request<{ bench_1rm_trend: object[]; whoop_trends: object }>('/progress'),
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
