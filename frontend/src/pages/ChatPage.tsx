import { useQuery, useQueryClient } from '@tanstack/react-query'
import { CloudUpload, FileText, LoaderCircle, Menu, Paperclip, TriangleAlert } from 'lucide-react'
import { useEffect, useRef, useState, type DragEvent } from 'react'
import { useNavigate, useOutletContext, useParams } from 'react-router'

import type { ShellContext } from '../App'
import { Answer } from '../components/Answer'
import { Composer } from '../components/Composer'
import { DocumentPreview, type PreviewTarget } from '../components/DocumentPreview'
import { chats as chatsApi } from '../lib/api'
import { streamAnswer } from '../lib/stream'
import type { ChatDetail, ChatDocument, Message, Source } from '../lib/types'

const ACCEPT = '.pdf,.docx,.txt'
const SUGGESTIONS = ['Summarise this document', 'What are the key dates and deadlines?', 'List the main points']

/** The answer that is currently streaming in, before it's saved. */
type Pending = {
  question: string
  stage: 'searching' | 'writing' | 'error'
  sources: Source[]
  text: string
  error?: string
}

type Upload = { id: number; name: string; error?: string }

export function ChatPage() {
  const { chatId } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { openSidebar, setSidebarCollapsed } = useOutletContext<ShellContext>()
  const fileInput = useRef<HTMLInputElement>(null)
  const bottom = useRef<HTMLDivElement>(null)
  const abort = useRef<AbortController | null>(null)

  const [pending, setPending] = useState<Pending | null>(null)
  const [lastCached, setLastCached] = useState<number | null>(null)
  const [uploads, setUploads] = useState<Upload[]>([])
  const [dragging, setDragging] = useState(false)
  const [hint, setHint] = useState<string | null>(null)
  const [preview, setPreview] = useState<PreviewTarget | null>(null)
  const previewOpen = preview !== null

  // Chat + document side by side is plenty: fold the sidebar into its icon
  // rail while a preview is open, and bring it back when it closes (or when
  // leaving this chat).
  useEffect(() => {
    if (!previewOpen) return
    setSidebarCollapsed(true)
    return () => setSidebarCollapsed(false)
  }, [previewOpen, setSidebarCollapsed])

  const { data: chat, isLoading, error } = useQuery({
    queryKey: ['chat', chatId],
    queryFn: () => chatsApi.get(chatId!),
    enabled: Boolean(chatId),
  })

  // Stop reading a stream if the user leaves the chat.
  useEffect(() => () => abort.current?.abort(), [])

  // Keep the newest message in view as text streams in.
  useEffect(() => {
    bottom.current?.scrollIntoView({ block: 'end' })
  }, [chat?.messages.length, pending?.text, pending?.stage])

  const hasDocuments = Boolean(chat?.documents.length)

  const openDocument = (doc: ChatDocument, highlight?: string) =>
    setPreview({ documentId: doc.id, filename: doc.filename, highlight })

  const openSource = (source: Source) => {
    const doc = chat?.documents.find((d) => d.id === source.document_id)
    if (doc) openDocument(doc, source.text)
  }

  async function uploadFiles(files: FileList | File[]) {
    setHint(null)
    let id = chatId
    for (const file of Array.from(files)) {
      const upload = { id: Date.now() + Math.random(), name: file.name }
      setUploads((u) => [...u, upload])
      try {
        if (!id) {
          // The first document creates the chat: no empty chats in the sidebar.
          id = (await chatsApi.create()).id
        }
        await chatsApi.upload(id, file)
        setUploads((u) => u.filter((x) => x.id !== upload.id))
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Upload failed.'
        setUploads((u) => u.map((x) => (x.id === upload.id ? { ...x, error: message } : x)))
      }
    }
    if (id) {
      await queryClient.invalidateQueries({ queryKey: ['chat', id] })
      queryClient.invalidateQueries({ queryKey: ['chats'] })
      if (id !== chatId) navigate(`/c/${id}`)
    }
  }

  async function ask(question: string) {
    if (!chatId || !hasDocuments) {
      setHint('Add a document first. Answers come only from this chat’s documents.')
      return
    }
    if (pending && pending.stage !== 'error') return
    setHint(null)
    setLastCached(null)
    setPending({ question, stage: 'searching', sources: [], text: '' })
    abort.current = new AbortController()

    try {
      await streamAnswer(
        chatId,
        question,
        {
          onSources: (sources) => setPending((p) => p && { ...p, stage: 'writing', sources }),
          onDelta: (text) => setPending((p) => p && { ...p, text: p.text + text }),
          onDone: (message: Message, cached) => {
            // Add both messages to the cached chat instead of refetching it, so
            // the streamed answer turns into the saved one without a flicker.
            queryClient.setQueryData<ChatDetail>(['chat', chatId], (old) =>
              old && {
                ...old,
                messages: [
                  ...old.messages,
                  { id: message.id - 1, role: 'user', content: question, sources: [], created_at: message.created_at },
                  message,
                ],
              },
            )
            if (cached) setLastCached(message.id)
            setPending(null)
            queryClient.invalidateQueries({ queryKey: ['chats'] }) // new title, new order
            queryClient.invalidateQueries({ queryKey: ['chat', chatId] })
          },
          onError: (detail) => setPending((p) => p && { ...p, stage: 'error', error: detail }),
        },
        abort.current.signal,
      )
    } catch (err) {
      if ((err as Error).name === 'AbortError') return
      setPending((p) => p && { ...p, stage: 'error', error: err instanceof Error ? err.message : 'Something went wrong.' })
    }
  }

  const onDrop = (e: DragEvent) => {
    e.preventDefault()
    setDragging(false)
    if (e.dataTransfer.files.length) uploadFiles(e.dataTransfer.files)
  }

  if (chatId && error) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
        <TriangleAlert className="size-8 text-danger" />
        <p className="font-medium">This chat couldn't be opened.</p>
        <p className="text-sm text-muted">{(error as Error).message}</p>
        <button onClick={() => navigate('/')} className="mt-2 rounded-xl border border-line px-4 py-2 text-sm hover:bg-raised">
          Start a new chat
        </button>
      </div>
    )
  }

  const messages = chat?.messages ?? []
  const empty = messages.length === 0 && !pending

  return (
    <div className="flex h-full">
    <div
      className="relative flex h-full min-w-0 flex-1 flex-col"
      onDragOver={(e) => {
        e.preventDefault()
        setDragging(true)
      }}
      onDragLeave={(e) => {
        if (e.currentTarget === e.target) setDragging(false)
      }}
      onDrop={onDrop}
    >
      <input
        ref={fileInput}
        type="file"
        accept={ACCEPT}
        multiple
        hidden
        onChange={(e) => {
          if (e.target.files?.length) uploadFiles(e.target.files)
          e.target.value = ''
        }}
      />

      <Header chat={chat} onAttach={() => fileInput.current?.click()} onOpenDocument={(d) => openDocument(d)} openSidebar={openSidebar} />

      <div className="flex-1 overflow-y-auto">
        {isLoading && chatId ? (
          <div className="flex h-full items-center justify-center text-muted">
            <LoaderCircle className="size-5 animate-spin" />
          </div>
        ) : empty ? (
          <EmptyState hasDocuments={hasDocuments} documentName={chat?.documents[0]?.filename} onBrowse={() => fileInput.current?.click()} onAsk={ask} />
        ) : (
          <div className="mx-auto max-w-3xl space-y-8 px-4 py-8">
            {messages.map((m) =>
              m.role === 'user' ? (
                <UserBubble key={m.id} text={m.content} />
              ) : (
                <Answer key={m.id} uid={String(m.id)} content={m.content} sources={m.sources} cached={m.id === lastCached} onOpenSource={openSource} />
              ),
            )}
            {pending && (
              <>
                <UserBubble text={pending.question} />
                <Answer
                  uid="pending"
                  content={pending.text}
                  sources={pending.sources}
                  streaming={pending.stage === 'writing'}
                  onOpenSource={openSource}
                  status={
                    pending.stage === 'error' ? (
                      <span className="flex items-center gap-2 text-danger">
                        <TriangleAlert className="size-4" /> {pending.error}
                        <button onClick={() => ask(pending.question)} className="ml-1 rounded-md border border-danger/40 px-2 py-0.5 text-xs hover:bg-danger/10">
                          Try again
                        </button>
                      </span>
                    ) : pending.stage === 'searching' ? (
                      <span className="shimmer">Searching your documents…</span>
                    ) : (
                      <span className="shimmer">Found {pending.sources.length} passages · writing answer…</span>
                    )
                  }
                />
                {pending.stage === 'error' && pending.text && <p className="pl-10 text-sm text-danger">{pending.error}</p>}
              </>
            )}
            <div ref={bottom} />
          </div>
        )}
      </div>

      {(uploads.length > 0 || hint) && (
        <div className="mx-auto w-full max-w-3xl space-y-1.5 px-4 pb-2">
          {uploads.map((u) => (
            <div key={u.id} className={`flex items-center gap-2 rounded-xl border px-3 py-2 text-sm ${u.error ? 'border-danger/40 text-danger' : 'border-line text-muted'}`}>
              {u.error ? <TriangleAlert className="size-4" /> : <LoaderCircle className="size-4 animate-spin text-accent-ink" />}
              <span className="truncate">{u.error ? `${u.name}: ${u.error}` : `Reading ${u.name}…`}</span>
              {u.error && (
                <button onClick={() => setUploads((x) => x.filter((y) => y.id !== u.id))} className="ml-auto text-xs underline">
                  Dismiss
                </button>
              )}
            </div>
          ))}
          {hint && <p className="rounded-xl bg-tint px-3 py-2 text-sm text-accent-ink">{hint}</p>}
        </div>
      )}

      <Composer
        placeholder={hasDocuments ? `Ask about ${chat!.documents.length === 1 ? chat!.documents[0].filename : `${chat!.documents.length} documents`}…` : 'Add a document to start asking…'}
        disabled={Boolean(pending && pending.stage !== 'error')}
        onSend={ask}
        onAttach={() => fileInput.current?.click()}
      />

      {dragging && (
        <div className="pointer-events-none absolute inset-3 z-30 flex flex-col items-center justify-center gap-2 rounded-3xl border-2 border-dashed border-accent bg-canvas/85 backdrop-blur-sm">
          <CloudUpload className="size-10 text-accent-ink" />
          <p className="font-display text-lg font-semibold">Drop to add to this chat</p>
          <p className="text-sm text-muted">PDF, Word or text files</p>
        </div>
      )}
    </div>
    {preview && (
      <div className="fixed inset-0 z-40 lg:static lg:z-auto lg:w-[42%] lg:max-w-[640px] lg:min-w-[380px]">
        <DocumentPreview target={preview} onClose={() => setPreview(null)} />
      </div>
    )}
    </div>
  )
}

function Header({ chat, onAttach, onOpenDocument, openSidebar }: { chat?: ChatDetail; onAttach: () => void; onOpenDocument: (d: ChatDocument) => void; openSidebar: () => void }) {
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState(false)
  const [title, setTitle] = useState('')

  const save = async () => {
    setEditing(false)
    const t = title.trim()
    if (!chat || !t || t === chat.title) return
    await chatsApi.rename(chat.id, t)
    queryClient.invalidateQueries({ queryKey: ['chat', chat.id] })
    queryClient.invalidateQueries({ queryKey: ['chats'] })
  }

  return (
    <header className="flex min-h-14 flex-wrap items-center gap-3 border-b border-line px-4 py-2">
      <button onClick={openSidebar} aria-label="Open chats" className="rounded-lg p-1.5 text-muted hover:bg-raised md:hidden">
        <Menu className="size-5" />
      </button>
      {editing && chat ? (
        <input
          autoFocus
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          onBlur={save}
          onKeyDown={(e) => {
            if (e.key === 'Enter') save()
            if (e.key === 'Escape') setEditing(false)
          }}
          className="min-w-0 flex-1 rounded-lg border border-accent bg-panel px-2 py-1 font-medium outline-none"
        />
      ) : (
        <button
          onClick={() => chat && (setTitle(chat.title), setEditing(true))}
          className="min-w-0 truncate rounded-lg px-1 py-1 text-left font-medium hover:bg-raised"
          title={chat ? 'Rename chat' : undefined}
        >
          {chat?.title ?? 'New chat'}
        </button>
      )}
      <div className="ml-auto flex flex-wrap items-center gap-2">
        {chat?.documents.map((d) => (
          <button
            key={d.id}
            onClick={() => onOpenDocument(d)}
            className="flex max-w-56 items-center gap-1.5 rounded-full border border-line bg-panel px-2.5 py-1 text-xs transition hover:border-accent/60"
            title={`Preview ${d.filename} · ${d.chunks} passages`}
          >
            <FileText className="size-3.5 shrink-0 text-accent-ink" />
            <span className="truncate">{d.filename}</span>
            <span className="text-faint">· {d.chunks}</span>
          </button>
        ))}
        <button onClick={onAttach} className="flex items-center gap-1.5 rounded-full border border-dashed border-line-strong px-2.5 py-1 text-xs text-muted transition hover:border-accent hover:text-ink">
          <Paperclip className="size-3.5" /> Add document
        </button>
      </div>
    </header>
  )
}

function UserBubble({ text }: { text: string }) {
  return (
    <div className="flex justify-end">
      <div className="max-w-[80%] rounded-2xl rounded-br-md bg-tint px-4 py-2.5 text-[15px] leading-relaxed whitespace-pre-wrap">{text}</div>
    </div>
  )
}

function EmptyState({ hasDocuments, documentName, onBrowse, onAsk }: { hasDocuments: boolean; documentName?: string; onBrowse: () => void; onAsk: (q: string) => void }) {
  return (
    <div className="mx-auto flex h-full max-w-xl flex-col items-center justify-center gap-6 px-6 py-10 text-center">
      {hasDocuments ? (
        <>
          <div>
            <h2 className="font-display text-2xl font-bold tracking-tight">Ask anything about {documentName ?? 'your documents'}</h2>
            <p className="mt-2 text-sm text-muted">Answers cite the exact passages they come from.</p>
          </div>
          <div className="flex flex-wrap justify-center gap-2">
            {SUGGESTIONS.map((s) => (
              <button key={s} onClick={() => onAsk(s)} className="rounded-full border border-line bg-panel px-3.5 py-1.5 text-sm text-muted transition hover:border-accent/60 hover:text-ink">
                {s}
              </button>
            ))}
          </div>
        </>
      ) : (
        <button
          onClick={onBrowse}
          className="group flex w-full flex-col items-center gap-3 rounded-3xl border-2 border-dashed border-line-strong bg-panel/50 px-6 py-14 transition hover:border-accent/70 hover:bg-tint/40"
        >
          <div className="flex size-14 items-center justify-center rounded-2xl bg-tint transition group-hover:scale-105">
            <CloudUpload className="size-7 text-accent-ink" />
          </div>
          <span className="font-display text-xl font-semibold">Drop a document to start</span>
          <span className="text-sm text-muted">PDF, Word or text · or click to browse</span>
        </button>
      )}
    </div>
  )
}
