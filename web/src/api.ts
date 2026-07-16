import type { ApiError, ClientConfig, HealthResponse, MetricsSnapshot, PlanAccepted, PlanResult, TripRequest } from './types'

export async function plan(req: TripRequest): Promise<PlanAccepted> {
  const resp = await fetch('/api/v1/plan', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })
  const data = (await resp.json()) as PlanAccepted | ApiError
  if ('error' in data) {
    const err = data as ApiError
    throw new Error(err.error?.message || '请求失败')
  }
  return data as PlanAccepted
}

export interface SSEHandlers {
  onStage?: (stage: string, message: string) => void
  onError?: (message: string) => void
}

export async function subscribeEvents(taskId: string, handlers: SSEHandlers): Promise<void> {
  try {
    const resp = await fetch(`/api/v1/plan/${taskId}/events`, { headers: { Accept: 'text/event-stream' } })
    if (!resp.ok || !resp.body) {
      handlers.onError?.('SSE 连接失败')
      return
    }
    const reader = resp.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''
    let stage = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const parts = buffer.split('\n\n')
      buffer = parts.pop() || ''
      for (const chunk of parts) {
        const lines = chunk.split('\n')
        let data = ''
        for (const line of lines) {
          if (line.startsWith('event: ')) stage = line.slice(7).trim()
          else if (line.startsWith('data: ')) data = line.slice(6)
        }
        if (data) handlers.onStage?.(stage, data)
      }
    }
  } catch {
    handlers.onError?.('SSE 订阅异常')
  }
}

export async function fetchItinerary(taskId: string): Promise<PlanResult | null> {
  const resp = await fetch(`/api/v1/plan/${taskId}`)
  if (resp.status === 404) return null
  const data = (await resp.json()) as PlanResult | ApiError
  if ('error' in data) {
    const err = data as ApiError
    throw new Error(err.error?.message || '查询失败')
  }
  return data as PlanResult
}

export async function pollItinerary(taskId: string, timeoutMs = 60000): Promise<PlanResult | null> {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    const result = await fetchItinerary(taskId)
    if (result) return result
    await new Promise((r) => setTimeout(r, 800))
  }
  return null
}

export async function fetchHealth(): Promise<HealthResponse> {
  const resp = await fetch('/health')
  return (await resp.json()) as HealthResponse
}

export async function fetchMetrics(): Promise<MetricsSnapshot> {
  const resp = await fetch('/metrics')
  return (await resp.json()) as MetricsSnapshot
}

export async function fetchConfig(): Promise<ClientConfig> {
  const resp = await fetch('/api/v1/config')
  return (await resp.json()) as ClientConfig
}