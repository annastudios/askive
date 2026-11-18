import { useEffect, useState } from 'react'

type Health = { status: string; checks?: Record<string, string> }

// Placeholder until the real interface is built: proves that React, Tailwind
// and the proxy to the FastAPI backend all work.
function App() {
  const [health, setHealth] = useState<Health | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch('/health')
      .then((res) => res.json())
      .then(setHealth)
      .catch((err: Error) => setError(err.message))
  }, [])

  return (
    <main className="flex min-h-screen items-center justify-center bg-zinc-950 p-6 text-zinc-100">
      <div className="w-full max-w-md rounded-2xl border border-white/10 bg-zinc-900 p-8 shadow-xl">
        <h1 className="text-2xl font-semibold tracking-tight">Askive v3</h1>
        <p className="mt-1 text-sm text-zinc-400">React + Vite + TypeScript + Tailwind</p>

        <div className="mt-6 rounded-lg bg-zinc-800/60 p-4 text-sm">
          <p className="font-medium">Backend health</p>
          {error && <p className="mt-2 text-red-400">Can't reach the API: {error}</p>}
          {!health && !error && <p className="mt-2 text-zinc-400">Checking…</p>}
          {health && (
            <ul className="mt-2 space-y-1">
              <li>
                status: <span className={health.status === 'ok' ? 'text-emerald-400' : 'text-amber-400'}>{health.status}</span>
              </li>
              {Object.entries(health.checks ?? {}).map(([name, result]) => (
                <li key={name} className="text-zinc-400">
                  {name}: {result}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </main>
  )
}

export default App
