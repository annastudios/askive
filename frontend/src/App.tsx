import { LoaderCircle } from 'lucide-react'
import { useEffect, useState } from 'react'
import { BrowserRouter, Navigate, Outlet, Route, Routes, useLocation, useNavigate, useParams } from 'react-router'

import { useAuth } from './auth'
import { Sidebar } from './components/Sidebar'
import { ChatPage } from './pages/ChatPage'
import { LoginPage } from './pages/LoginPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Shell />}>
          <Route index element={<ChatRoute />} />
          <Route path="c/:chatId" element={<ChatRoute />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}

/** What the layout offers the chat pages inside it. */
export type ShellContext = {
  openSidebar: () => void
  setSidebarCollapsed: (collapsed: boolean) => void
}

/** Sign-in gate + sidebar layout around every chat page. */
function Shell() {
  const { user, loading } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)

  // Ctrl+K (Cmd+K on Mac) starts a new chat from anywhere.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        navigate('/')
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [navigate])

  // Close the phone-sized sidebar after navigating.
  useEffect(() => setSidebarOpen(false), [location.pathname])

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center text-muted">
        <LoaderCircle className="size-6 animate-spin" />
      </div>
    )
  }
  if (!user) return <LoginPage />

  return (
    <div className="flex h-full overflow-hidden">
      <div className="hidden md:block">
        <Sidebar collapsed={sidebarCollapsed} onToggleCollapsed={() => setSidebarCollapsed((c) => !c)} />
      </div>
      {sidebarOpen && (
        <div className="fixed inset-0 z-40 flex md:hidden">
          <Sidebar onNavigate={() => setSidebarOpen(false)} />
          <button aria-label="Close chats" className="flex-1 bg-black/60" onClick={() => setSidebarOpen(false)} />
        </div>
      )}
      <main className="min-w-0 flex-1 bg-canvas">
        <Outlet context={{ openSidebar: () => setSidebarOpen(true), setSidebarCollapsed } satisfies ShellContext} />
      </main>
    </div>
  )
}

/** A fresh ChatPage per chat, so one chat's streaming state never leaks into another. */
function ChatRoute() {
  const { chatId } = useParams()
  return <ChatPage key={chatId ?? 'new'} />
}
