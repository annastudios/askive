import { describe, expect, it, vi } from 'vitest'

import { streamAnswer, type StreamHandlers } from './stream'

/** A fetch() response whose body arrives in the given network chunks. */
function streamingResponse(chunks: string[]): Response {
  const encoder = new TextEncoder()
  const body = new ReadableStream({
    start(controller) {
      for (const c of chunks) controller.enqueue(encoder.encode(c))
      controller.close()
    },
  })
  return new Response(body, { status: 200, headers: { 'Content-Type': 'text/event-stream' } })
}

function recordingHandlers() {
  const events: string[] = []
  const handlers: StreamHandlers = {
    onSources: (sources, cached) => events.push(`sources:${sources.length}:${cached}`),
    onDelta: (text) => events.push(`delta:${text}`),
    onDone: (message, cached) => events.push(`done:${message.id}:${cached}`),
    onError: (detail) => events.push(`error:${detail}`),
  }
  return { events, handlers }
}

const sources = 'event: sources\ndata: {"sources": [{"document_id": "d1", "text": "Refunds take 30 days."}], "cached": false}\n\n'
const done = 'event: done\ndata: {"message": {"id": 7, "role": "assistant", "content": "Hi", "sources": [], "created_at": "2026-11-18T10:00:00Z"}, "cached": false}\n\n'

describe('streamAnswer', () => {
  it('turns server-sent events into handler calls, in order', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => streamingResponse([sources, 'event: delta\ndata: {"text": "Hel"}\n\n', 'event: delta\ndata: {"text": "lo"}\n\n', done])))
    const { events, handlers } = recordingHandlers()

    await streamAnswer('chat-1', 'Hello?', handlers)

    expect(events).toEqual(['sources:1:false', 'delta:Hel', 'delta:lo', 'done:7:false'])
  })

  it('copes with a network chunk that ends in the middle of an event', async () => {
    const whole = sources + 'event: delta\ndata: {"text": "split"}\n\n' + done
    const pieces = [whole.slice(0, 30), whole.slice(30, 151), whole.slice(151)]
    vi.stubGlobal('fetch', vi.fn(async () => streamingResponse(pieces)))
    const { events, handlers } = recordingHandlers()

    await streamAnswer('chat-1', 'Hello?', handlers)

    expect(events).toEqual(['sources:1:false', 'delta:split', 'done:7:false'])
  })

  it('reports an error event', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => streamingResponse([sources, 'event: error\ndata: {"detail": "Quota exhausted."}\n\n'])))
    const { events, handlers } = recordingHandlers()

    await streamAnswer('chat-1', 'Hello?', handlers)

    expect(events).toEqual(['sources:1:false', 'error:Quota exhausted.'])
  })

  it('sends the question with the login token', async () => {
    localStorage.setItem('askive_token', 'secret-token')
    const fetchMock = vi.fn(async () => streamingResponse([done]))
    vi.stubGlobal('fetch', fetchMock)

    await streamAnswer('chat-9', 'Why?', recordingHandlers().handlers)

    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toBe('/chats/chat-9/messages/stream')
    expect(new Headers(init.headers).get('Authorization')).toBe('Bearer secret-token')
    expect(JSON.parse(init.body as string)).toEqual({ question: 'Why?' })
  })
})
