import { useQuery } from '@tanstack/react-query'
import { FileText, LoaderCircle, TriangleAlert, X } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'

import { documents } from '../lib/api'

export type PreviewTarget = { documentId: string; filename: string; highlight?: string }

/**
 * Finds a passage inside the document text. Chunking joined sentences with
 * single spaces, while the original may have line breaks, so whitespace is
 * matched loosely. Falls back to the passage's opening words.
 */
export function findPassage(text: string, passage: string): [number, number] | null {
  const words = passage.trim().split(/\s+/).filter(Boolean)
  const escape = (w: string) => w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  for (const count of [words.length, 12, 6]) {
    if (count > words.length || count === 0) continue
    const match = new RegExp(words.slice(0, count).map(escape).join('\\s+')).exec(text)
    if (match) return [match.index, match.index + match[0].length]
  }
  return null
}

export function DocumentPreview({ target, onClose }: { target: PreviewTarget; onClose: () => void }) {
  const isPdf = target.filename.toLowerCase().endsWith('.pdf')
  // A passage to show means the text view, where it can be highlighted.
  const [tab, setTab] = useState<'original' | 'text'>(isPdf && !target.highlight ? 'original' : 'text')

  useEffect(() => {
    setTab(isPdf && !target.highlight ? 'original' : 'text')
  }, [target, isPdf])

  return (
    <aside className="flex h-full w-full flex-col border-l border-line bg-sidebar">
      <header className="flex items-center gap-2 border-b border-line px-4 py-3">
        <FileText className="size-4 shrink-0 text-accent-ink" />
        <span className="min-w-0 flex-1 truncate text-sm font-medium" title={target.filename}>
          {target.filename}
        </span>
        {isPdf && (
          <div className="flex rounded-lg border border-line p-0.5 text-xs">
            {(['original', 'text'] as const).map((t) => (
              <button key={t} onClick={() => setTab(t)} className={`rounded-md px-2.5 py-1 transition ${tab === t ? 'bg-tint text-ink' : 'text-muted hover:text-ink'}`}>
                {t === 'original' ? 'PDF' : 'Text'}
              </button>
            ))}
          </div>
        )}
        <button onClick={onClose} aria-label="Close preview" className="rounded-lg p-1.5 text-muted transition hover:bg-raised hover:text-ink">
          <X className="size-4" />
        </button>
      </header>
      <div className="min-h-0 flex-1">{tab === 'original' ? <PdfView documentId={target.documentId} /> : <TextView target={target} />}</div>
    </aside>
  )
}

function PdfView({ documentId }: { documentId: string }) {
  const [url, setUrl] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let objectUrl: string | null = null
    documents
      .fileUrl(documentId)
      .then((u) => setUrl((objectUrl = u)))
      .catch((e: Error) => setError(e.message))
    return () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [documentId])

  if (error) return <Problem message={error} />
  if (!url) return <Loading />
  return <iframe src={url} title="Document preview" className="h-full w-full border-0 bg-white" />
}

function TextView({ target }: { target: PreviewTarget }) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['document-text', target.documentId],
    queryFn: () => documents.text(target.documentId),
    staleTime: Infinity, // a document's text never changes
  })
  const mark = useRef<HTMLElement>(null)

  const range = useMemo(() => (data && target.highlight ? findPassage(data.text, target.highlight) : null), [data, target.highlight])

  useEffect(() => {
    mark.current?.scrollIntoView({ block: 'center', behavior: 'smooth' })
  }, [range])

  if (error) return <Problem message={(error as Error).message} />
  if (isLoading || !data) return <Loading />

  const text = data.text
  return (
    <div className="h-full overflow-y-auto px-5 py-4">
      {target.highlight && !range && <p className="mb-3 rounded-lg bg-raised px-3 py-2 text-xs text-muted">The cited passage couldn't be located exactly in this text.</p>}
      <div className="text-[13.5px] leading-7 whitespace-pre-wrap text-muted">
        {range ? (
          <>
            {text.slice(0, range[0])}
            <mark ref={mark} className="rounded bg-accent/25 px-0.5 text-ink ring-1 ring-accent/50">
              {text.slice(range[0], range[1])}
            </mark>
            {text.slice(range[1])}
          </>
        ) : (
          text
        )}
      </div>
    </div>
  )
}

function Loading() {
  return (
    <div className="flex h-full items-center justify-center text-muted">
      <LoaderCircle className="size-5 animate-spin" />
    </div>
  )
}

function Problem({ message }: { message: string }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-2 px-6 text-center">
      <TriangleAlert className="size-6 text-muted" />
      <p className="text-sm text-muted">{message}</p>
    </div>
  )
}
