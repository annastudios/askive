import { LoaderCircle } from 'lucide-react'
import { useState, type FormEvent } from 'react'

import { useAuth } from '../auth'
import { LogoMark } from '../components/Logo'

export function LoginPage() {
  const { signIn, signUp } = useAuth()
  const [mode, setMode] = useState<'signin' | 'signup'>('signin')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const isSignIn = mode === 'signin'

  async function submit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      await (isSignIn ? signIn : signUp)(email.trim(), password)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="relative flex min-h-full items-center justify-center overflow-hidden px-4 py-12">
      {/* Soft violet glow behind the card */}
      <div className="pointer-events-none absolute -top-40 left-1/2 h-[480px] w-[720px] -translate-x-1/2 rounded-full bg-accent/15 blur-[120px]" />

      <form onSubmit={submit} className="relative w-full max-w-sm rounded-2xl border border-line bg-panel/90 p-8 shadow-2xl backdrop-blur">
        <div className="flex flex-col items-center gap-3 text-center">
          <LogoMark size={44} />
          <h1 className="font-display text-2xl font-bold tracking-tight">{isSignIn ? 'Welcome back' : 'Create your account'}</h1>
          <p className="text-sm text-muted">Chat with your documents</p>
        </div>

        <div className="mt-8 space-y-3">
          <label className="block">
            <span className="mb-1.5 block text-xs font-medium text-muted">Email</span>
            <input
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="name@company.com"
              className="w-full rounded-xl border border-line bg-canvas px-3.5 py-2.5 text-sm outline-none transition placeholder:text-faint focus:border-accent focus:ring-4 focus:ring-accent/15"
            />
          </label>
          <label className="block">
            <span className="mb-1.5 block text-xs font-medium text-muted">Password</span>
            <input
              type="password"
              required
              minLength={isSignIn ? undefined : 8}
              autoComplete={isSignIn ? 'current-password' : 'new-password'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={isSignIn ? '••••••••' : 'At least 8 characters'}
              className="w-full rounded-xl border border-line bg-canvas px-3.5 py-2.5 text-sm outline-none transition placeholder:text-faint focus:border-accent focus:ring-4 focus:ring-accent/15"
            />
          </label>
        </div>

        {error && (
          <p role="alert" className="mt-4 rounded-lg bg-danger/10 px-3 py-2 text-sm text-danger">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={busy}
          className="mt-6 flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-accent to-accent-2 px-4 py-2.5 text-sm font-semibold text-white shadow-[0_8px_30px_-8px_var(--accent)] transition hover:brightness-110 disabled:opacity-60"
        >
          {busy && <LoaderCircle className="size-4 animate-spin" />}
          {isSignIn ? 'Sign in' : 'Create account'}
        </button>

        <p className="mt-5 text-center text-sm text-muted">
          {isSignIn ? 'New here?' : 'Already have an account?'}{' '}
          <button
            type="button"
            onClick={() => {
              setMode(isSignIn ? 'signup' : 'signin')
              setError(null)
            }}
            className="font-medium text-accent-ink hover:underline"
          >
            {isSignIn ? 'Create an account' : 'Sign in'}
          </button>
        </p>
      </form>
    </main>
  )
}
