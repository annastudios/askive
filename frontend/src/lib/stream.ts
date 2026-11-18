import { api } from './api'
import type { Message, Source } from './types'

export type StreamHandlers = {
  onSources: (sources: Source[], cached: boolean) => void
  onDelta: (text: string) => void
  onDone: (message: Message, cached: boolean) => void
  onError: (detail: string) => void
}

/**
 * Asks a question and reads the answer as it streams in.
 *
 * The server sends Server-Sent Events: blocks of `event: <name>` and
 * `data: <json>` separated by a blank line. The browser's EventSource can't
 * send a POST with a login token, so this reads the response body directly.
 */
export async function streamAnswer(chatId: string, question: string, handlers: StreamHandlers, signal?: AbortSignal) {
  const res = await api(`/chats/${chatId}/messages/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
    signal,
  })
  const reader = res.body!.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += value
    // A network chunk can end mid-event: only handle complete blocks.
    let end: number
    while ((end = buffer.indexOf('\n\n')) !== -1) {
      dispatch(buffer.slice(0, end), handlers)
      buffer = buffer.slice(end + 2)
    }
  }
}

function dispatch(block: string, h: StreamHandlers) {
  let event = 'message'
  let data = ''
  for (const line of block.split('\n')) {
    if (line.startsWith('event: ')) event = line.slice(7)
    else if (line.startsWith('data: ')) data += line.slice(6)
  }
  const payload = data ? JSON.parse(data) : {}
  if (event === 'sources') h.onSources(payload.sources, payload.cached)
  else if (event === 'delta') h.onDelta(payload.text)
  else if (event === 'done') h.onDone(payload.message, payload.cached)
  else if (event === 'error') h.onError(payload.detail)
}
