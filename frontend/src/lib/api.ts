import type { ChatDetail, ChatDocument, ChatSummary, User } from './types'

const TOKEN_KEY = 'askive_token'

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function setToken(token: string | null) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token)
    else localStorage.removeItem(TOKEN_KEY)
  } catch {
    // Storage unavailable (private mode): you'll just sign in again next time.
  }
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

// Fired when the server rejects the token, so the app can return to sign-in.
export const SIGNED_OUT_EVENT = 'askive:signed-out'

export async function errorMessage(res: Response): Promise<string> {
  try {
    const body = await res.json()
    if (typeof body.detail === 'string') return body.detail
    if (Array.isArray(body.detail)) {
      return body.detail.map((d: { loc: string[]; msg: string }) => `${d.loc.at(-1)}: ${d.msg}`).join('; ')
    }
  } catch {
    // not JSON
  }
  return `Something went wrong (${res.status}).`
}

/** fetch() with the login token attached; throws ApiError on failure. */
export async function api(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers)
  const token = getToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const res = await fetch(path, { ...init, headers })
  if (res.status === 401 && token) {
    setToken(null)
    window.dispatchEvent(new Event(SIGNED_OUT_EVENT))
  }
  if (!res.ok) throw new ApiError(res.status, await errorMessage(res))
  return res
}

const json = (body: unknown): RequestInit => ({
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})

export const auth = {
  async login(email: string, password: string): Promise<string> {
    // OAuth2's form field is called "username"; Askive puts the email in it.
    const res = await api('/auth/login', { method: 'POST', body: new URLSearchParams({ username: email, password }) })
    return (await res.json()).access_token
  },
  async register(email: string, password: string): Promise<void> {
    await api('/auth/register', { method: 'POST', ...json({ email, password }) })
  },
  async me(): Promise<User> {
    return (await api('/auth/me')).json()
  },
}

export const chats = {
  async list(): Promise<ChatSummary[]> {
    return (await api('/chats')).json()
  },
  async get(id: string): Promise<ChatDetail> {
    return (await api(`/chats/${id}`)).json()
  },
  async create(): Promise<ChatSummary> {
    return (await api('/chats', { method: 'POST' })).json()
  },
  async rename(id: string, title: string): Promise<ChatSummary> {
    return (await api(`/chats/${id}`, { method: 'PATCH', ...json({ title }) })).json()
  },
  async remove(id: string): Promise<void> {
    await api(`/chats/${id}`, { method: 'DELETE' })
  },
  async upload(id: string, file: File): Promise<ChatDocument> {
    const form = new FormData()
    form.append('file', file)
    return (await api(`/chats/${id}/documents`, { method: 'POST', body: form })).json()
  },
}

export const documents = {
  async text(id: string): Promise<{ filename: string; text: string }> {
    return (await api(`/documents/${id}/text`)).json()
  },
  /** The original file as a local URL the browser can show (e.g. in an iframe). */
  async fileUrl(id: string): Promise<string> {
    const blob = await (await api(`/documents/${id}/file`)).blob()
    return URL.createObjectURL(blob)
  },
}
