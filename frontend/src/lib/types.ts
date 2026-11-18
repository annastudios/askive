// Shapes of the JSON the FastAPI backend returns (see app/models/schemas.py).

export type User = { id: string; email: string }

export type ChatSummary = {
  id: string
  title: string
  created_at: string
  updated_at: string
}

export type ChatDocument = { id: string; filename: string; chunks: number }

/** A retrieved passage. document_id is null for answers saved before v3 recorded it. */
export type Source = { document_id: string | null; text: string }

export type Message = {
  id: number
  role: 'user' | 'assistant'
  content: string
  sources: Source[]
  created_at: string
}

export type ChatDetail = ChatSummary & {
  documents: ChatDocument[]
  messages: Message[]
}
