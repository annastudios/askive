import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import App from './App'
import { AuthProvider } from './auth'

const user = { id: 'u1', email: 'sam@example.com' }
const savedChats = [{ id: 'c1', title: 'Refund policy questions', created_at: '2026-11-18T09:00:00Z', updated_at: '2026-11-18T09:00:00Z' }]

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })

/** A stand-in for the FastAPI backend: answers by method + path. */
function fakeBackend(routes: Record<string, () => Response>) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const key = `${init?.method ?? 'GET'} ${String(input)}`
    return routes[key]?.() ?? json({ detail: 'Not Found' }, 404)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function renderApp() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </QueryClientProvider>,
  )
}

describe('<App>', () => {
  it('asks a signed-out visitor to sign in', () => {
    fakeBackend({})
    renderApp()
    expect(screen.getByRole('heading', { name: 'Welcome back' })).toBeInTheDocument()
  })

  it('signs in and shows the saved chats', async () => {
    const fetchMock = fakeBackend({
      'POST /auth/login': () => json({ access_token: 'tok-123', token_type: 'bearer' }),
      'GET /auth/me': () => json(user),
      'GET /chats': () => json(savedChats),
    })
    renderApp()

    await userEvent.type(screen.getByPlaceholderText('name@company.com'), 'sam@example.com')
    await userEvent.type(screen.getByPlaceholderText('••••••••'), 'correct horse')
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))

    expect((await screen.findAllByText('Refund policy questions')).length).toBeGreaterThan(0)
    expect(localStorage.getItem('askive_token')).toBe('tok-123')
    const login = fetchMock.mock.calls.find(([url]) => url === '/auth/login')!
    expect(String(login[1]!.body)).toBe('username=sam%40example.com&password=correct+horse')
  })

  it("shows the server's message when sign-in fails", async () => {
    fakeBackend({ 'POST /auth/login': () => json({ detail: 'Wrong email or password.' }, 401) })
    renderApp()

    await userEvent.type(screen.getByPlaceholderText('name@company.com'), 'sam@example.com')
    await userEvent.type(screen.getByPlaceholderText('••••••••'), 'nope')
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Wrong email or password.')
  })

  it('goes straight to the chats when a saved token is still valid', async () => {
    localStorage.setItem('askive_token', 'tok-123')
    fakeBackend({ 'GET /auth/me': () => json(user), 'GET /chats': () => json(savedChats) })
    renderApp()

    expect((await screen.findAllByText('Refund policy questions')).length).toBeGreaterThan(0)
    expect(screen.queryByRole('heading', { name: 'Welcome back' })).not.toBeInTheDocument()
  })

  it('returns to sign-in when the saved token has expired', async () => {
    localStorage.setItem('askive_token', 'old-token')
    fakeBackend({ 'GET /auth/me': () => json({ detail: 'Token expired.' }, 401) })
    renderApp()

    expect(await screen.findByRole('heading', { name: 'Welcome back' })).toBeInTheDocument()
    expect(localStorage.getItem('askive_token')).toBeNull()
  })
})
