import type { SupabaseClient } from '@supabase/supabase-js'

export class BackendApiError extends Error {
  status: number
  detail: string

  constructor(status: number, detail: string) {
    super(`Backend API error (${status}): ${detail}`)
    this.name = 'BackendApiError'
    this.status = status
    this.detail = detail
  }
}

function resolveApiBase(): string {
  const base = process.env.NEXT_PUBLIC_API_URL?.trim() || '/api'
  return base.endsWith('/') ? base.slice(0, -1) : base
}

function resolvePath(path: string): string {
  if (!path) {
    return '/'
  }

  return path.startsWith('/') ? path : `/${path}`
}

function extractDetail(payload: unknown, fallback: string): string {
  if (!payload) {
    return fallback
  }

  if (typeof payload === 'string') {
    return payload
  }

  if (typeof payload === 'object' && payload !== null && 'detail' in payload) {
    const detail = (payload as { detail?: unknown }).detail
    return typeof detail === 'string' && detail.trim() ? detail : fallback
  }

  return fallback
}

async function getBearerToken(supabase: SupabaseClient): Promise<string> {
  const {
    data: { session },
    error,
  } = await supabase.auth.getSession()

  if (error || !session?.access_token) {
    throw new BackendApiError(401, 'Missing session token')
  }

  return session.access_token
}

async function parseResponseBody(response: Response): Promise<unknown> {
  const raw = await response.text()
  if (!raw) {
    return null
  }

  try {
    return JSON.parse(raw)
  } catch {
    return raw
  }
}

export async function backendRequest<T>(
  supabase: SupabaseClient,
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const token = await getBearerToken(supabase)
  const headers = new Headers(init.headers || {})
  headers.set('Authorization', `Bearer ${token}`)
  headers.set('Accept', 'application/json')

  if (init.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  const response = await fetch(`${resolveApiBase()}${resolvePath(path)}`, {
    ...init,
    headers,
  })

  const parsed = await parseResponseBody(response)

  if (!response.ok) {
    throw new BackendApiError(
      response.status,
      extractDetail(parsed, `Request failed (${response.status})`),
    )
  }

  return parsed as T
}

export async function backendGet<T>(
  supabase: SupabaseClient,
  path: string,
): Promise<T> {
  return backendRequest<T>(supabase, path, { method: 'GET' })
}

export async function backendPost<T>(
  supabase: SupabaseClient,
  path: string,
  body?: unknown,
): Promise<T> {
  return backendRequest<T>(supabase, path, {
    method: 'POST',
    body: body === undefined ? undefined : JSON.stringify(body),
  })
}
