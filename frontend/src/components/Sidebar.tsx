import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Ellipsis, LogOut, Pencil, Plus, Search, Trash2, X } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { NavLink, useNavigate, useParams } from 'react-router'

import { useAuth } from '../auth'
import { chats as chatsApi } from '../lib/api'
import type { ChatSummary } from '../lib/types'
import { Logo } from './Logo'

const GROUPS = ['Today', 'Yesterday', 'Previous 7 days', 'Older'] as const

function groupOf(iso: string): (typeof GROUPS)[number] {
  const day = 24 * 60 * 60 * 1000
  const startOfToday = new Date().setHours(0, 0, 0, 0)
  const t = new Date(iso).getTime()
  if (t >= startOfToday) return 'Today'
  if (t >= startOfToday - day) return 'Yesterday'
  if (t >= startOfToday - 7 * day) return 'Previous 7 days'
  return 'Older'
}

export function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const { user, signOut } = useAuth()
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const { data: chats = [], isLoading } = useQuery({ queryKey: ['chats'], queryFn: chatsApi.list })

  const grouped = useMemo(() => {
    const q = query.trim().toLowerCase()
    const visible = q ? chats.filter((c) => c.title.toLowerCase().includes(q)) : chats
    return GROUPS.map((g) => [g, visible.filter((c) => groupOf(c.updated_at) === g)] as const).filter(([, list]) => list.length)
  }, [chats, query])

  const newChat = () => {
    navigate('/')
    onNavigate?.()
  }

  return (
    <aside className="flex h-full w-72 flex-col border-r border-line bg-sidebar">
      <div className="flex items-center justify-between px-4 pt-4 pb-3">
        <Logo />
      </div>

      <div className="space-y-2 px-3">
        <button
          onClick={newChat}
          className="group flex w-full items-center gap-2 rounded-xl border border-line bg-panel px-3 py-2 text-sm font-medium transition hover:border-accent/50 hover:bg-tint"
        >
          <Plus className="size-4 text-accent-ink" />
          New chat
          <kbd className="ml-auto rounded-md border border-line px-1.5 py-0.5 font-sans text-[10px] text-muted">Ctrl K</kbd>
        </button>
        <label className="flex items-center gap-2 rounded-xl border border-line px-3 py-2 text-sm focus-within:border-accent/60">
          <Search className="size-4 text-faint" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search chats"
            className="w-full bg-transparent outline-none placeholder:text-faint"
          />
        </label>
      </div>

      <nav className="mt-3 flex-1 space-y-4 overflow-y-auto px-3 pb-3">
        {isLoading && <p className="px-2 text-sm text-faint">Loading chats…</p>}
        {!isLoading && chats.length === 0 && (
          <p className="px-2 text-sm leading-relaxed text-faint">Your chats will show up here. Start by dropping a document into a new chat.</p>
        )}
        {!isLoading && chats.length > 0 && grouped.length === 0 && <p className="px-2 text-sm text-faint">No chats match "{query}".</p>}
        {grouped.map(([group, list]) => (
          <div key={group}>
            <p className="px-2 pb-1 text-[11px] font-medium tracking-wide text-faint">{group}</p>
            <ul className="space-y-0.5">
              {list.map((chat) => (
                <ChatItem key={chat.id} chat={chat} onNavigate={onNavigate} />
              ))}
            </ul>
          </div>
        ))}
      </nav>

      <div className="flex items-center gap-2 border-t border-line px-3 py-3">
        <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-tint text-xs font-semibold text-accent-ink uppercase">
          {user?.email[0]}
        </div>
        <span className="min-w-0 flex-1 truncate text-sm text-muted" title={user?.email}>
          {user?.email}
        </span>
        <button onClick={signOut} aria-label="Sign out" className="rounded-lg p-2 text-muted transition hover:bg-raised hover:text-ink">
          <LogOut className="size-4" />
        </button>
      </div>
    </aside>
  )
}

function ChatItem({ chat, onNavigate }: { chat: ChatSummary; onNavigate?: () => void }) {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const { chatId } = useParams()
  const [menuOpen, setMenuOpen] = useState(false)
  const [mode, setMode] = useState<'view' | 'rename' | 'confirm-delete'>('view')
  const [title, setTitle] = useState(chat.title)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!menuOpen) return
    const close = (e: MouseEvent) => {
      if (!menuRef.current?.contains(e.target as Node)) setMenuOpen(false)
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [menuOpen])

  const rename = useMutation({
    mutationFn: (t: string) => chatsApi.rename(chat.id, t),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['chats'] })
      queryClient.invalidateQueries({ queryKey: ['chat', chat.id] })
    },
  })
  const remove = useMutation({
    mutationFn: () => chatsApi.remove(chat.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['chats'] })
      queryClient.removeQueries({ queryKey: ['chat', chat.id] })
      if (chatId === chat.id) navigate('/')
    },
  })

  if (mode === 'rename') {
    const save = () => {
      const t = title.trim()
      if (t && t !== chat.title) rename.mutate(t)
      setMode('view')
    }
    return (
      <li>
        <input
          autoFocus
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          onBlur={save}
          onKeyDown={(e) => {
            if (e.key === 'Enter') save()
            if (e.key === 'Escape') {
              setTitle(chat.title)
              setMode('view')
            }
          }}
          className="w-full rounded-lg border border-accent bg-panel px-2.5 py-2 text-sm outline-none"
        />
      </li>
    )
  }

  if (mode === 'confirm-delete') {
    return (
      <li className="rounded-lg border border-danger/40 bg-danger/5 p-2.5 text-sm">
        <p className="text-ink">Delete "{chat.title}"?</p>
        <p className="mt-0.5 text-xs text-muted">Its messages are removed for good.</p>
        <div className="mt-2 flex gap-2">
          <button onClick={() => remove.mutate()} className="rounded-md bg-danger px-2.5 py-1 text-xs font-medium text-white hover:brightness-110">
            Delete
          </button>
          <button onClick={() => setMode('view')} className="rounded-md px-2.5 py-1 text-xs text-muted hover:bg-raised">
            Cancel
          </button>
        </div>
      </li>
    )
  }

  return (
    <li className="group relative">
      <NavLink
        to={`/c/${chat.id}`}
        onClick={onNavigate}
        className={({ isActive }) =>
          `block truncate rounded-lg py-2 pr-9 pl-2.5 text-sm transition ${isActive ? 'bg-tint font-medium text-ink' : 'text-muted hover:bg-raised hover:text-ink'}`
        }
        title={chat.title}
      >
        {chat.title}
      </NavLink>
      <div ref={menuRef} className="absolute top-1 right-1">
        <button
          onClick={() => setMenuOpen((o) => !o)}
          aria-label={`Options for ${chat.title}`}
          className={`rounded-md p-1.5 text-faint transition hover:text-ink ${menuOpen ? 'opacity-100' : 'opacity-0 group-hover:opacity-100 focus:opacity-100'}`}
        >
          {menuOpen ? <X className="size-3.5" /> : <Ellipsis className="size-3.5" />}
        </button>
        {menuOpen && (
          <div className="absolute right-0 z-20 mt-1 w-36 overflow-hidden rounded-xl border border-line bg-raised p-1 shadow-xl">
            <button onClick={() => (setMenuOpen(false), setTitle(chat.title), setMode('rename'))} className="flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-sm hover:bg-tint">
              <Pencil className="size-3.5" /> Rename
            </button>
            <button onClick={() => (setMenuOpen(false), setMode('confirm-delete'))} className="flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-sm text-danger hover:bg-danger/10">
              <Trash2 className="size-3.5" /> Delete
            </button>
          </div>
        )}
      </div>
    </li>
  )
}
