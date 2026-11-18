import { ArrowUp, Paperclip } from 'lucide-react'
import { useEffect, useRef, useState, type KeyboardEvent } from 'react'

type Props = {
  placeholder: string
  disabled?: boolean
  onSend: (question: string) => void
  onAttach: () => void
}

/** Enter sends, Shift+Enter adds a new line; the box grows with the text. */
export function Composer({ placeholder, disabled, onSend, onAttach }: Props) {
  const [text, setText] = useState('')
  const ref = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`
  }, [text])

  useEffect(() => {
    if (!disabled) ref.current?.focus()
  }, [disabled])

  const send = () => {
    const q = text.trim()
    if (!q || disabled) return
    onSend(q)
    setText('')
  }

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      send()
    }
  }

  return (
    <div className="mx-auto w-full max-w-3xl px-4 pb-4">
      <div className="flex items-end gap-2 rounded-2xl border border-line-strong bg-panel p-2 pl-3 shadow-[0_8px_40px_-12px_rgba(0,0,0,0.5)] transition focus-within:border-accent/60 focus-within:ring-4 focus-within:ring-accent/10">
        <button type="button" onClick={onAttach} aria-label="Attach a document" className="mb-1 rounded-lg p-1.5 text-muted transition hover:bg-raised hover:text-ink">
          <Paperclip className="size-4.5" />
        </button>
        <textarea
          ref={ref}
          rows={1}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder={placeholder}
          aria-label="Your question"
          className="max-h-[200px] flex-1 resize-none bg-transparent py-2 text-[15px] outline-none placeholder:text-faint"
        />
        <button
          type="button"
          onClick={send}
          disabled={disabled || !text.trim()}
          aria-label="Send"
          className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-accent to-accent-2 text-white shadow-[0_6px_20px_-6px_var(--accent)] transition hover:brightness-110 disabled:from-raised disabled:to-raised disabled:text-faint disabled:shadow-none"
        >
          <ArrowUp className="size-4.5" strokeWidth={2.5} />
        </button>
      </div>
      <p className="mt-2 text-center text-[11px] text-faint">Answers come only from this chat's documents</p>
    </div>
  )
}
