/** web/src/api/client.ts 模块。 */
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
  if (ct.includes('application/json')) return res.json() as Promise<T>
  return res as T
}

/** 处理 jsonBody 相关逻辑。 */
export function jsonBody(body: unknown): Pick<RequestInit, 'headers' | 'body'> {
  return {
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }
}

