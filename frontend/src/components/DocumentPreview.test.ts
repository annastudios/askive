import { describe, expect, it } from 'vitest'

import { findPassage } from './DocumentPreview'

const text = 'Returns and refunds. Items can be returned within 30 days\nof delivery for a full refund.\n\nShipping takes five days.'

describe('findPassage', () => {
  it('finds a passage even when the line breaks differ', () => {
    // Chunks join sentences with single spaces; the document has a line break.
    const passage = 'Items can be returned within 30 days of delivery for a full refund.'
    const range = findPassage(text, passage)!
    expect(text.slice(...range)).toBe('Items can be returned within 30 days\nof delivery for a full refund.')
  })

  it('falls back to the opening words when the rest differs', () => {
    const passage = 'Returns and refunds. Items can be returned within 30 days of delivery, conditions apply.'
    const range = findPassage(text, passage)!
    expect(text.slice(...range).startsWith('Returns and refunds.')).toBe(true)
  })

  it('treats special characters literally', () => {
    expect(findPassage('Price: $5 (excl. tax).', 'Price: $5 (excl. tax).')).toEqual([0, 22])
  })

  it('returns null when the passage is not in the text', () => {
    expect(findPassage(text, 'Penguins live in Antarctica and eat fish.')).toBeNull()
  })
})
