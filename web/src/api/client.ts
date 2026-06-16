/** web/src/api/client.ts 模块。 */
export class ApiError extends Error {
  status: number
  data: unknown

  constructor(message: string, status: number, data: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.data = data
  }
}

export async function api<T = any>(url: string, opts: RequestInit = {}): Promise<T> {
  const res = await fetch(url, {
    credentials: 'include',
    ...opts,
    headers: {
      ...(opts.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...(opts.headers || {}),
    },
  })

  const ct = res.headers.get('Content-Type') || ''
  if (ct.includes('application/json')) {
    const data = await res.json()
    if (!res.ok) {
      if (res.status === 401) {
        window.dispatchEvent(new CustomEvent('votx-session-expired', { detail: data }))
      }
      throw new ApiError(data?.error || `请求失败 (${res.status})`, res.status, data)
    }
    return data as T
  }
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    if (res.status === 401) {
      window.dispatchEvent(new CustomEvent('votx-session-expired', { detail: { error: text || '会话已失效' } }))
    }
    throw new ApiError(text || `请求失败 (${res.status})`, res.status, text)
  }
  return res as T
}

/** 处理 jsonBody 相关逻辑。 */
export function jsonBody(body: unknown): Pick<RequestInit, 'headers' | 'body'> {
  return {
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }
}
