import { Check, ChevronDown, Copy, FileSearch, Sparkles, Zap } from 'lucide-react'
import { useMemo, useState, type ReactNode } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

import type { Source } from '../lib/types'

const CITATION = /\[(\d{1,2}(?:\s*,\s*\d{1,2})*)\](?!\()/g

/**
 * Turns citations like [2] or [1, 3] into markdown links (#cite-2) so the
 * renderer below can draw them as clickable chips. A real markdown link,
 * "[text](url)", is left alone.
 */
export function linkCitations(text: string): string {
  return text.replace(CITATION, (_, nums: string) =>
    nums
      .split(',')
      .map((n) => `[${n.trim()}](#cite-${n.trim()})`)
      .join(''),
  )
}

/** The passage numbers an answer cites, in order of first mention. */
export function citedNumbers(text: string): number[] {
  const seen: number[] = []
  for (const match of text.matchAll(CITATION)) {
    for (const n of match[1].split(',').map((x) => Number(x.trim()))) {
      if (!seen.includes(n)) seen.push(n)
    }
  }
  return seen
}

type Props = {
  /** Unique per answer on the page, for the source cards' scroll targets. */
  uid: string
  content: string
  sources: Source[]
  streaming?: boolean
  cached?: boolean
  status?: ReactNode
  /** Opens a passage in the document preview. */
  onOpenSource?: (source: Source) => void
}

export function Answer({ uid, content, sources, streaming, cached, status, onOpenSource }: Props) {
  const [active, setActive] = useState<number | null>(null)
  const [showAll, setShowAll] = useState(false)
  const [copied, setCopied] = useState(false)

  const cited = useMemo(() => citedNumbers(content).filter((n) => n >= 1 && n <= sources.length), [content, sources.length])
  // Only what the answer actually cites, unless the user asks for everything.
  const shown = showAll ? sources.map((_, i) => i + 1) : cited
  const hidden = sources.length - shown.length

  const openSource = (n: number) => {
    setActive(n)
    const source = sources[n - 1]
    if (source.document_id && onOpenSource) onOpenSource(source)
    else document.getElementById(`source-${uid}-${n}`)?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  }

  const copy = async () => {
    await navigator.clipboard.writeText(content.replace(CITATION, '').trim())
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  return (
    <div className="flex gap-3">
      <div className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-accent to-accent-2">
        <Sparkles className="size-3.5 text-white" />
      </div>
      {/* @container: the passage grid responds to the space this answer has, not the window. */}
      <div className="@container min-w-0 flex-1 space-y-3">
        {status && !content && <div className="pt-1 text-sm">{status}</div>}

        {content && (
          <div className={`answer text-[15px] leading-7 text-ink/90 ${streaming ? 'caret' : ''}`}>
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                a: ({ href, children }) => {
                  const n = href?.startsWith('#cite-') ? Number(href.slice(6)) : null
                  if (n && n >= 1 && n <= sources.length) {
                    return (
                      <button
                        type="button"
                        onClick={() => openSource(n)}
                        className={`mx-0.5 inline-flex h-[1.35em] min-w-[1.35em] -translate-y-px items-center justify-center rounded-md px-1 align-middle text-[11px] font-semibold transition ${
                          active === n ? 'bg-accent text-white' : 'bg-tint text-accent-ink hover:bg-accent/30'
                        }`}
                        aria-label={`Show source ${n}`}
                      >
                        {n}
                      </button>
                    )
                  }
                  // An ordinary link (or a citation to a passage that doesn't exist).
                  return href?.startsWith('#cite-') ? (
                    <span className="text-faint">[{children}]</span>
                  ) : (
                    <a href={href} target="_blank" rel="noreferrer" className="text-accent-ink underline">
                      {children}
                    </a>
                  )
                },
              }}
            >
              {linkCitations(content)}
            </ReactMarkdown>
          </div>
        )}

        {shown.length > 0 && (
          <div className={`grid gap-2 ${shown.length > 1 ? '@lg:grid-cols-2' : ''}`}>
            {shown.map((n) => {
              const source = sources[n - 1]
              const canOpen = Boolean(source.document_id && onOpenSource)
              return (
                <button
                  key={n}
                  id={`source-${uid}-${n}`}
                  type="button"
                  onClick={() => (canOpen ? openSource(n) : setActive(active === n ? null : n))}
                  className={`group rounded-xl border p-3 text-left text-xs leading-relaxed transition ${
                    active === n ? 'border-accent bg-tint/60' : 'border-line bg-panel hover:border-line-strong'
                  }`}
                >
                  <span className="mb-1 flex items-center gap-1.5 font-medium text-accent-ink">
                    <span className="flex size-4 items-center justify-center rounded bg-tint text-[10px]">{n}</span>
                    Passage {n}
                    {canOpen && (
                      <span className="ml-auto flex items-center gap-1 font-normal text-faint opacity-0 transition group-hover:opacity-100">
                        <FileSearch className="size-3" /> Open in document
                      </span>
                    )}
                  </span>
                  <span className={`text-muted ${active === n ? '' : 'line-clamp-2'}`}>{source.text}</span>
                </button>
              )
            })}
          </div>
        )}

        {!streaming && sources.length > 0 && (showAll || hidden > 0) && (
          <button onClick={() => setShowAll((s) => !s)} className="flex items-center gap-1 text-xs text-faint transition hover:text-ink">
            <ChevronDown className={`size-3.5 transition ${showAll ? 'rotate-180' : ''}`} />
            {showAll ? 'Show only cited passages' : cited.length ? `Show all ${sources.length} passages` : `Show the ${sources.length} passages used`}
          </button>
        )}

        {content && !streaming && (
          <div className="flex items-center gap-3 text-xs text-faint">
            <button onClick={copy} className="flex items-center gap-1 transition hover:text-ink">
              {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
              {copied ? 'Copied' : 'Copy'}
            </button>
            {cached && (
              <span className="flex items-center gap-1 text-accent-ink" title="Answered from the cache: same question, same documents">
                <Zap className="size-3.5" /> Instant (cached)
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
